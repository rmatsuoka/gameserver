import json
import uuid
from enum import Enum, IntEnum
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound
from sqlalchemy.sql.expression import select

from .db import engine


class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げる"""


class SafeUser(BaseModel):
    """token を含まないUser"""

    id: int
    name: str
    leader_card_id: int

    class Config:
        orm_mode = True


def create_user(name: str, leader_card_id: int) -> str:
    """Create new user and returns their token"""
    token = str(uuid.uuid4())
    # NOTE: tokenが衝突したらリトライする必要がある.
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO `user` (name, token, leader_card_id) VALUES (:name, :token, :leader_card_id)"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )
        # print(result)
    return token


def _get_user_by_token(conn, token: str) -> Optional[SafeUser]:
    # TODO: 実装
    result = conn.execute(
        text("SELECT `id`, `name`, `leader_card_id` FROM `user` WHERE `token`=:token"),
        dict(token=token),
    )
    try:
        row = result.one()
    except NoResultFound:
        return None
    return SafeUser.from_orm(row)


def get_user_by_token(token: str) -> Optional[SafeUser]:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def update_user(token: str, name: str, leader_card_id: int) -> None:
    # このコードを実装してもらう
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        conn.execute(
            text(
                "UPDATE `user` SET `name` = :name, `leader_card_id` = :leader_card_id WHERE `id` = :id"
            ),
            dict(name=name, leader_card_id=leader_card_id, id=user.id),
        )


# Room
RoomMaxUserCount = 4


class LiveDifficulty(IntEnum):
    normal = 1
    hard = 2


class JoinRoomResult(IntEnum):
    Ok = 1
    RoomFull = 2
    Disbanded = 3
    OtherError = 4


class WaitRoomStatus(IntEnum):
    Waiting = 1
    LiveStart = 2
    Dissoution = 3


class RoomInfo(BaseModel):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int


class RoomUser(BaseModel):
    user_id: int
    name: str
    leader_card_id: int
    select_difficulty: LiveDifficulty
    is_me: bool
    is_host: bool


class ResultUser(BaseModel):
    user_id: int
    judge_count_list: list[int]
    score: int


def _add_user_in_room(
    conn, room_id: int, user_id: int, select_difficulty: LiveDifficulty
):
    result = conn.execute(
        text(
            "INSERT INTO `room_user` (room_id, user_id, select_difficulty) VALUES (:room_id, :user_id, :select_difficulty)"
        ),
        {
            "room_id": room_id,
            "user_id": user_id,
            "select_difficulty": int(select_difficulty),
        },
    )


def create_room_with_host(
    token: str, live_id: int, select_difficulty: LiveDifficulty
) -> int:
    """Create new user and returns their token"""
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken

        result = conn.execute(
            text(
                "INSERT INTO `room` (live_id, status, owner) VALUES (:live_id, :status, :owner)"
            ),
            {
                "live_id": live_id,
                "status": int(WaitRoomStatus.Waiting),
                "owner": user.id,
            },
        )
        room_id = result.lastrowid
        _add_user_in_room(conn, room_id, user.id, select_difficulty)
    return room_id


def list_room(live_id: int) -> list[RoomInfo]:
    with engine.begin() as conn:
        if live_id == 0:
            result = conn.execute(
                text(
                    """
                    SELECT r.`id`, r.`live_id`, COUNT(*)
                    FROM `room` r JOIN `room_user` ru
                    ON r.`id` = ru.`room_id`
                    WHERE r.`status` = :status
                    GROUP BY r.`id`
                """
                ),
                {"status": int(WaitRoomStatus.Waiting), "live_id": live_id},
            )
        else:
            result = conn.execute(
                text(
                    """
                    SELECT r.`id`, r.`live_id`, COUNT(*)
                    FROM `room` r JOIN `room_user` ru
                    ON r.`id` = ru.`room_id`
                    WHERE r.`status` = :status AND r.`live_id` = :live_id
                    GROUP BY r.`id`
                """
                ),
                {"status": int(WaitRoomStatus.Waiting), "live_id": live_id},
            )

    ret = []
    for row in result:
        ret.append(
            RoomInfo(
                room_id=row.id,
                live_id=row.live_id,
                joined_user_count=row["COUNT(*)"],
                max_user_count=4,
            )
        )
    return ret


def join_room(
    token: str, room_id: int, select_difficulty: LiveDifficulty
) -> JoinRoomResult:
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        room_status = conn.execute(
            text(
                """
                SELECT r.`status`, COUNT(*)
                FROM `room` r JOIN `room_user` ru
                ON r.`id` = ru.`room_id`
                WHERE r.`id` = :room_id
                GROUP BY r.`id`
                """
            ),
            {"room_id": room_id},
        ).one()
        if room_status["COUNT(*)"] >= RoomMaxUserCount:
            return JoinRoomResult.RoomFull
        elif room_status.status != WaitRoomStatus.Waiting:
            return JoinRoomResult.Disbanded
        _add_user_in_room(conn, room_id, user.id, select_difficulty)
        return JoinRoomResult.Ok


def wait_room(room_id: int, token: str) -> tuple[WaitRoomStatus, list[RoomUser]]:
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        room = conn.execute(
            text("SELECT `status`, `owner` FROM `room` WHERE id = :room_id"),
            {"room_id": room_id},
        ).one()
        result = conn.execute(
            text(
                """SELECT u.`id`, u.`name`, u.`leader_card_id`, ru.`select_difficulty`
                FROM `user` u JOIN `room_user` ru
                ON u.`id` = ru.`user_id`
                WHERE ru.`room_id` = :room_id"""
            ),
            {"room_id": room_id},
        )
    ret = []
    for row in result:
        ret.append(
            RoomUser(
                user_id=row.id,
                name=row.name,
                leader_card_id=row.leader_card_id,
                select_difficulty=row.select_difficulty,
                is_me=True if user.id == row.id else False,
                is_host=True if room.owner == row.id else False,
            )
        )
    return room.status, ret

def start_room(token: str, room_id: int):
    with engine.begin() as conn:
        # user = _get_user_by_token(conn, token)
        # if user is None:
        #     raise InvalidToken
        # result = conn.execute(
        #     text(
        #         """
        #         SELECT `owner`
        #         FROM `room`
        #         WHERE `id` = :room_id
        #         """
        #     ),
        #     {"room_id": room_id},
        # )
        # if result.one().owner != user.id:
        #     raise InvalidToken
        result = conn.execute(
            text(
                """UPDATE `room`
                SET `status` = :status
                WHERE `id` = :room_id"""
            ),
            {
                "status": int(WaitRoomStatus.LiveStart),
                "room_id": room_id,
            },
        )

from enum import Enum

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from . import model
from .model import (
    JoinRoomResult,
    LiveDifficulty,
    ResultUser,
    RoomInfo,
    RoomUser,
    SafeUser,
    WaitRoomStatus,
    result_room,
)

app = FastAPI()

# Sample APIs


@app.get("/")
async def root():
    return {"message": "Hello World"}


# User APIs


class UserCreateRequest(BaseModel):
    user_name: str
    leader_card_id: int


class UserCreateResponse(BaseModel):
    user_token: str


@app.post("/user/create", response_model=UserCreateResponse)
def user_create(req: UserCreateRequest):
    """新規ユーザー作成"""
    token = model.create_user(req.user_name, req.leader_card_id)
    return UserCreateResponse(user_token=token)


bearer = HTTPBearer()


def get_auth_token(cred: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    assert cred is not None
    if not cred.credentials:
        raise HTTPException(status_code=401, detail="invalid credential")
    return cred.credentials


@app.get("/user/me", response_model=SafeUser)
def user_me(token: str = Depends(get_auth_token)):
    user = model.get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=404)
    # print(f"user_me({token=}, {user=})")
    return user


class Empty(BaseModel):
    pass


@app.post("/user/update", response_model=Empty)
def update(req: UserCreateRequest, token: str = Depends(get_auth_token)):
    """Update user attributes"""
    # print(req)
    model.update_user(token, req.user_name, req.leader_card_id)
    return {}


# Room APIs


class RoomID(BaseModel):
    room_id: int


class RoomCreateRequest(BaseModel):
    live_id: int
    select_difficulty: LiveDifficulty


@app.post("/room/create", response_model=RoomID)
def room_create(req: RoomCreateRequest, token: str = Depends(get_auth_token)):
    room = model.create_room_with_host(token, req.live_id, req.select_difficulty)
    return RoomID(room_id=room)


class RoomListRequest(BaseModel):
    live_id: int


class RoomListResponse(BaseModel):
    room_info_list: list[RoomInfo]


@app.post("/room/list", response_model=RoomListResponse)
def room_list(req: RoomListRequest, token: str = Depends(get_auth_token)):
    lst = model.list_room(req.live_id)
    return RoomListResponse(room_info_list=lst)


# /room/join
class RoomJoinRequest(BaseModel):
    room_id: int
    select_difficulty: LiveDifficulty


class RoomJoinResponse(BaseModel):
    join_room_result: JoinRoomResult


@app.post("/room/join", response_model=RoomJoinResponse)
def room_join(req: RoomJoinRequest, token: str = Depends(get_auth_token)):
    result = model.join_room(token, req.room_id, req.select_difficulty)
    return RoomJoinResponse(join_room_result=result)


# /room/wait
class RoomWaitResponse(BaseModel):
    status: WaitRoomStatus
    room_user_list: list[RoomUser]


@app.post("/room/wait", response_model=RoomWaitResponse)
def room_wait(req: RoomID, token: str = Depends(get_auth_token)):
    status, lst = model.wait_room(req.room_id, token)
    return RoomWaitResponse(status=status, room_user_list=lst)


# /room/start
@app.post("/room/start", response_model=Empty)
def room_start(req: RoomID, token: str = Depends(get_auth_token)):
    model.start_room(token, req.room_id)
    return {}


# /room/end
class RoomEndRequest(BaseModel):
    room_id: int
    judge_count_list: list[int]
    score: int


@app.post("/room/end", response_model=Empty)
def room_end(req: RoomEndRequest, token: str = Depends(get_auth_token)):
    model.end_room(token, req.room_id, req.judge_count_list, req.score)
    return {}


# /room/result
class RoomResultResponse(BaseModel):
    result_user_list: list[ResultUser]


@app.post("/room/result", response_model=RoomResultResponse)
def room_result(req: RoomID, token: str = Depends(get_auth_token)):
    lst = model.result_room(req.room_id)
    return RoomResultResponse(result_user_list=lst)


@app.post("/room/leave", response_model=Empty)
def room_leave(req: RoomID, token: str = Depends(get_auth_token)):
    model.leave_room(token, req.room_id)
    return {}

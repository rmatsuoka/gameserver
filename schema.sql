DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) DEFAULT NULL,
  `token` varchar(255) DEFAULT NULL,
  `leader_card_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token` (`token`)
);

DROP TABLE IF EXISTS `room`;
CREATE TABLE `room` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `live_id` int NOT NULL,
  `owner` bigint NOT NULL,
  `status` int NOT NULL,
  PRIMARY KEY (`id`)
);

DROP TABLE IF EXISTS `room_user`;
CREATE TABLE `room_user` (
  `room_id` bigint NOT NULL,
  `user_id` bigint NOT NULL,
  `score` int,
  `select_difficulty` int NOT NULL,
  `judge_count_list` varchar(255),
  PRIMARY KEY (`room_id`, `user_id`)
);
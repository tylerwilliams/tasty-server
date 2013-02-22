-- CREATE DATABASE tastydb;
use tastydb;


-- check if user already exists / add a new user / get user perms
-- SELECT `email` FROM `users` WHERE email = 'williams.tyler@gmail.com';
-- INSERT INTO `users`  (`id`, `email`, `status`, `last_login`, `date_joined`, `shared_secret`, `consumer_key`) VALUES
--      (1, 'williams.tyler@gmail.com', 'active', '12345', '12345', 'aaabbbccc', 'abcabcabcd')

CREATE TABLE `users` (
    `id`                int NOT NULL AUTO_INCREMENT,
    `login`             varchar(255) NOT NULL,
    `service`           varchar(100),
    `email`             varchar(255) DEFAULT NULL,
    `status`            varchar(100) NOT NULL DEFAULT 'active',
    `last_login`        bigint NOT NULL,
    `date_joined`       bigint NOT NULL,
    `shared_secret`     varchar(255) NOT NULL,
    `consumer_key`      varchar(255) NOT NULL,
    PRIMARY KEY (`id`) USING BTREE,
    UNIQUE KEY (`login`, `service`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- show me my tastes / add a new taste
-- SELECT * FROM tastes WHERE user_id = 1;
-- INSERT INTO `tastes` (`source`, `artist_name`, `song_name`, `duration`) VALUES ('rdio', 'u2', 'somesong', 12345);

CREATE TABLE `tastes` (
    `id`                int NOT NULL AUTO_INCREMENT,
    `user_id`           int NOT NULL,
    `source`            varchar(255) NOT NULL,
    `artist_name`       varchar(255) NOT NULL,
    `song_name`         varchar(255) NOT NULL,
    `timestamp`         bigint NOT NULL,
    `release_name`      varchar(255) DEFAULT NULL,
    `duration`          double DEFAULT NULL,
    `rating`            bigint DEFAULT NULL,
    `play_count`        bigint DEFAULT NULL,
    `favorite`          tinyint(1) DEFAULT NULL,
    `skip`              tinyint(1) DEFAULT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    PRIMARY KEY (`id`, `user_id`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE `fingerprints` (
    `id`                int NOT NULL AUTO_INCREMENT,
    `taste_id`          int NOT NULL,
    `code`              BLOB NOT NULL,
    FOREIGN KEY (taste_id) REFERENCES tastes(id) ON DELETE CASCADE,
    PRIMARY KEY (`id`, `taste_id`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
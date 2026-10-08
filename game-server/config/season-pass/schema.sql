CREATE TABLE IF NOT EXISTS season_pass_progress (
 season_id VARCHAR(40) NOT NULL, player_id INT NOT NULL, tier INT NOT NULL DEFAULT 0,
 xp INT NOT NULL DEFAULT 0, boost_granted BOOLEAN NOT NULL DEFAULT 0,
 PRIMARY KEY(season_id,player_id)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS season_pass_missions (
 season_id VARCHAR(40) NOT NULL, player_id INT NOT NULL, mission_id VARCHAR(40) NOT NULL,
 period_key VARCHAR(40) NOT NULL, progress INT NOT NULL DEFAULT 0, awarded BOOLEAN NOT NULL DEFAULT 0,
 PRIMARY KEY(season_id,player_id,mission_id,period_key)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS season_pass_claims (
 season_id VARCHAR(40) NOT NULL, player_id INT NOT NULL, reward_level INT NOT NULL, track INT NOT NULL,
 mail_id INT NOT NULL, item_id INT NOT NULL, quantity BIGINT NOT NULL, claimed_at BIGINT NOT NULL,
 PRIMARY KEY(season_id,player_id,reward_level,track)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS season_pass_requests (
 request_id VARCHAR(64) NOT NULL PRIMARY KEY, season_id VARCHAR(40) NOT NULL, player_id INT NOT NULL,
 action VARCHAR(20) NOT NULL, result VARCHAR(500) NOT NULL, created_at BIGINT NOT NULL
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS season_pass_rivals (
 season_id VARCHAR(40) NOT NULL, player_id INT NOT NULL, victim_id INT NOT NULL, credited_at BIGINT NOT NULL,
 PRIMARY KEY(season_id,player_id,victim_id)
) ENGINE=InnoDB;

-- Tables to be created:

CREATE TABLE "cluster" (
  id                bigserial PRIMARY KEY,
  position          point NOT NULL,
  group_id          bigint UNIQUE REFERENCES "group"
--  users_in_cluster  bigint
);
CREATE INDEX position_idx ON "cluster" USING gist (box(position,position));
CREATE INDEX group_id_idx ON "cluster.group_id"


--This table represent the list of users in a cluster
--CREATE TABLE cluster_user (
--  cluster_id  bigint NOT NULL REFERENCES "cluster",
--  user_id     bigint NOT NULL REFERENCES "user",
--  PRIMARY KEY(user_id)
--);
--CREATE INDEX cluster_idx ON cluster_user(cluster_id);
--ALTER TABLE "cluster" ADD CONSTRAINT users_in_cluster_fk FOREIGN KEY (users_in_cluster)
--    REFERENCES "cluster_user";


-- Tables to be altered:
-- "user"
ALTER TABLE "user" ADD COLUMN location point;
ALTER TABLE "user" ADD COLUMN location_timestamp timestamp NOT NULL DEFAULT '1970-01-01 00:00:00';
ALTER TABLE "user" ADD COLUMN cluster_id bigint REFERENCES "cluster";
CREATE INDEX cluster_id_idx ON "user" (cluster_id);

-- "group"
ALTER TABLE "group" ADD COLUMN password text; -- also update unison-recsys/libs/libunison/libunison/models.py
ALTER TABLE "group" ADD COLUMN update_time timestamp NOT NULL DEFAULT now();
ALTER TABLE "group" ADD COLUMN automatic boolean NOT NULL DEFAULT FALSE;

CREATE INDEX automatic_idx ON "group" (automatic);

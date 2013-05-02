-- Unison back-end database schema.
-- Uses some PostgreSQL specific stuff.
--
-- Create the database with:
--     createdb -E UTF8 unison  # UTF-8 encoding.

CREATE OR REPLACE FUNCTION update_time_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.update_time = now(); 
    RETURN NEW;
END;
$$ language 'plpgsql';


CREATE TABLE "user" (
  id             bigserial PRIMARY KEY,
  creation_time  timestamp NOT NULL DEFAULT now(),
  email          text UNIQUE NOT NULL,
  email_valid    boolean NOT NULL DEFAULT FALSE,
  password       text NOT NULL,
  nickname       text,
  group_id       bigint,
  model          text -- Base64 encoded.
);
CREATE INDEX user_group_idx ON "user"(group_id);


CREATE TABLE "group" (
  id             bigserial PRIMARY KEY,
  creation_time  timestamp NOT NULL DEFAULT now(),
  name           text NOT NULL,
  coordinates    point NOT NULL, -- Geographic coordinates.
  master         bigint REFERENCES "user",
  active         boolean NOT NULL DEFAULT FALSE
);
-- Add the foreign key constraint on user(group_id).
ALTER TABLE "user" ADD CONSTRAINT group_fk FOREIGN KEY (group_id)
    REFERENCES "group";


CREATE TABLE track (
  id             bigserial PRIMARY KEY,
  creation_time  timestamp NOT NULL DEFAULT now(),
  update_time    timestamp NOT NULL DEFAULT now(),
  artist         text NOT NULL,
  title          text NOT NULL,
  image          text, -- As a URL.
  listeners      integer, -- Number of listeners on last.fm.
  tags           text, -- JSON array.
  features       text, -- Base64 encoded.
  UNIQUE (artist, title)
);
CREATE INDEX track_artist_title_idx ON track(artist, title);
CREATE TRIGGER track_update_time_trigger BEFORE UPDATE
    ON track FOR EACH ROW EXECUTE PROCEDURE update_time_column();


-- Entries in this table are not meant to be updated, except for the "valid"
-- field. When something changes (track gets deleted, new local_id, new rating,
-- ...) we should instead invalidate the data and create a new row.
CREATE TABLE lib_entry (
  id             bigserial PRIMARY KEY,
  creation_time  timestamp NOT NULL DEFAULT now(),
  update_time    timestamp NOT NULL DEFAULT now(),
  user_id        bigint NOT NULL REFERENCES "user",
  track_id       bigint NOT NULL REFERENCES track,
  local_id       integer,
  valid          boolean NOT NULL DEFAULT FALSE,
  local          boolean NOT NULL DEFAULT FALSE,
  rating         integer,
  listenings     integer NOT NULL DEFAULT 0
);
CREATE INDEX lib_entry_user_idx ON lib_entry(user_id);
CREATE INDEX lib_entry_track_idx ON lib_entry(track_id);
CREATE TRIGGER lib_entry_update_time_trigger BEFORE UPDATE
    ON lib_entry FOR EACH ROW EXECUTE PROCEDURE update_time_column();
ALTER TABLE lib_entry ADD COLUMN listenings integer NOT NULL DEFAULT 0; -- Stores the number of times a track is played


CREATE TYPE group_event_type
    AS ENUM ('play', 'rating', 'join', 'leave', 'skip', 'master');
CREATE TABLE group_event (
  id             bigserial PRIMARY KEY,
  creation_time  timestamp NOT NULL DEFAULT now(),
  user_id        bigint REFERENCES "user",
  group_id       bigint REFERENCES "group",
  event_type     group_event_type NOT NULL,
  payload        text -- JSON encoded.
);
CREATE INDEX group_event_group_idx ON group_event(group_id);
CREATE INDEX group_event_creation_time_idx ON group_event(creation_time);

-- Following tables are used for single-user mode
CREATE TABLE playlist (
  id             bigserial PRIMARY KEY,
  creation_time  timestamp NOT NULL DEFAULT now(),
  update_time    timestamp NOT NULL DEFAULT now(),
  author_id      bigint NOT NULL REFERENCES "user",
  title          text NOT NULL,
  image          text, -- As a URL (user selectable, by default an image of a randomly picked up track in the playlist).
  size           integer NOT NULL DEFAULT 0,
  tracks         text, -- JSONArray of lib_entry ids
  listeners      integer DEFAULT 0, -- Number of listeners (users who added this playlist to their own library).
  seeds          text NOT NULL, -- JSONObject
  features       text NOT NULL, -- Base64 encoded
  avg_rating     real,
  valid          boolean NOT NULL DEFAULT FALSE,
  shared         boolean NOT NULL DEFAULT FALSE -- to other GroupStreamer users
);
CREATE INDEX playlist_title_idx ON playlist(title);
CREATE INDEX playlist_size_idx ON playlist(size);
CREATE TRIGGER playlist_update_time_trigger BEFORE UPDATE
    ON playlist FOR EACH ROW EXECUTE PROCEDURE update_time_column();


CREATE TABLE pllib_entry (
  id             bigserial PRIMARY KEY,
  creation_time  timestamp NOT NULL DEFAULT now(),
  update_time    timestamp NOT NULL DEFAULT now(),
  user_id        bigint NOT NULL REFERENCES "user",
  playlist_id    bigint NOT NULL REFERENCES playlist,
  local_id       bigint,
  valid          boolean NOT NULL DEFAULT FALSE,
  --local          boolean NOT NULL DEFAULT FALSE,
  sync           boolean NOT NULL DEFAULT FALSE, -- If true, asks to keep this playlist in sync with the original one (user_id is not creator_id)
  rating         integer,
  comment        text
);
CREATE INDEX pllib_entry_user_idx ON pllib_entry(user_id);
CREATE INDEX pllib_entry_playlist_idx ON pllib_entry(playlist_id);
CREATE TRIGGER pllib_entry_update_time_trigger BEFORE UPDATE
    ON pllib_entry FOR EACH ROW EXECUTE PROCEDURE update_time_column();

CREATE TABLE top_tag (
  id             bigserial PRIMARY KEY,
  creation_time  timestamp NOT NULL DEFAULT now(),
  name           text NOT NULL, -- from last.fm API
  ref_id         bigint NOT NULL, -- hash of name
  features       text NOT NULL, -- Base64 encoded
  count          bigint, -- from last.fm API
  url            text -- from last.fm API,
);
CREATE INDEX top_tag_ref_id_idx ON top_tag(ref_id);

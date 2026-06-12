-- Schema definitions for soccer_2016
-- Auto-extracted from sources/soccer_2016/postgres.sh

-- Table: extra_runs
CREATE TABLE IF NOT EXISTS extra_runs (
    Match_Id      INTEGER,
    Over_Id       INTEGER,
    Ball_Id       INTEGER,
    Extra_Type_Id INTEGER,
    Extra_Runs    INTEGER,
    Innings_No    INTEGER,
    PRIMARY KEY (Match_Id, Over_Id, Ball_Id, Innings_No)
);

-- Table: wicket_taken
CREATE TABLE IF NOT EXISTS wicket_taken (
    Match_Id   INTEGER,
    Over_Id    INTEGER,
    Ball_Id    INTEGER,
    Player_Out INTEGER,
    Kind_Out   INTEGER,
    Fielders   Float,
    Innings_No INTEGER,
    PRIMARY KEY (Match_Id, Over_Id, Ball_Id, Innings_No)
);

-- Table: ball_by_ball
CREATE TABLE IF NOT EXISTS ball_by_ball (
    Match_Id                 INTEGER,
    Over_Id                  INTEGER,
    Ball_Id                  INTEGER,
    Innings_No               INTEGER,
    Team_Batting             INTEGER,
    Team_Bowling             INTEGER,
    Striker_Batting_Position INTEGER,
    Striker                  INTEGER,
    Non_Striker              INTEGER,
    Bowler                   INTEGER,
    PRIMARY KEY (Match_Id, Over_Id, Ball_Id, Innings_No)
);


SET ECHO OFF

-- Initialize
ECHO INIT;

SET AUTOCOMMIT ON;

-- Define
ECHO DEFINE;

-- Drop tutorial tables if they exist
DROP TABLE IF EXISTS custmast;

ECHO Create table...;
CREATE TABLE custmast (
   cm_custnumb CHAR(4),
   cm_custzipc CHAR(9),
   cm_custstat CHAR(2),
   cm_custrtng CHAR(1),
   cm_custname VARCHAR(47),
   cm_custaddr VARCHAR(47),
   cm_custcity VARCHAR(47));

-- Manage
ECHO MANAGE;

ECHO Add records...;
INSERT INTO custmast VALUES ('1000', '92867', 'CA', '1', 'Bryan Williams', '2999 Regency', 'Orange');
INSERT INTO custmast VALUES ('1001', '61434', 'CT', '1', 'Michael Jordan', '13 Main', 'Harford');
INSERT INTO custmast VALUES ('1002', '73677', 'GA', '1', 'Joshua Brown', '4356 Cambridge', 'Atlanta');
INSERT INTO custmast VALUES ('1003', '10034', 'MO', '1', 'Keyon Dooling', '19771 Park Avenue', 'Columbia');

ECHO Display records...;
SELECT cm_custnumb "Number", cm_custname "Name" FROM custmast;

-- Done
ECHO DONE;

-- end of custmast1.sql

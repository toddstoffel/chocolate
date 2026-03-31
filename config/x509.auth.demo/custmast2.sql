SET ECHO OFF

-- Initialize
ECHO INIT;

SET AUTOCOMMIT ON;

-- Define
ECHO DEFINE;

ECHO Update record...;
UPDATE custmast SET cm_custname = 'KEYON DOOLING' WHERE cm_custnumb = '1003';

ECHO Delete record...;
DELETE FROM custmast where cm_custnumb=1000;

ECHO Add record...;
INSERT INTO custmast VALUES ('1000', '92867', 'CA', '1', 'Bryan Williams', '2999 Regency', 'Orange');

COMMIT WORK;
-- Done
ECHO DONE;

-- end of ISQL_Tutorial2.sql

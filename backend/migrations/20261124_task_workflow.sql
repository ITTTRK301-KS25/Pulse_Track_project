ALTER TABLE tasks DROP CHECK ck_tasks_status;

ALTER TABLE tasks
    ADD CONSTRAINT ck_tasks_status
    CHECK (status IN ('TODO', 'IN_PROGRESS', 'TESTING_QA', 'IN_REVIEW', 'DONE'));

-- Pre-v2 (0.1.0) sample rows for testing the 19.0.2.0.0 migrations on a CLONE.
-- Applied by `scripts/upgrade.sh --legacy-fixture` before the upgrade. Never run on real data.
-- Idempotent: every row is tagged "LEGACY-" and skipped if it already exists.
-- Needs at least one student (for the partner) and one opportunity.

BEGIN;

-- One student per legacy application status (a student can only hold one open placement).
INSERT INTO internship_student (name, partner_id, university_id, student_id, active, create_date, write_date)
SELECT 'LEGACY ' || s.status, p.partner_id, p.university_id, 'LEGACY-' || s.status, TRUE, now(), now()
  FROM (VALUES ('documentation'), ('agreement'), ('approved'), ('placed')) AS s(status)
 CROSS JOIN (SELECT partner_id, university_id FROM internship_student ORDER BY id LIMIT 1) p
 WHERE NOT EXISTS (SELECT 1 FROM internship_student WHERE student_id = 'LEGACY-' || s.status);

INSERT INTO internship_application (name, student_id, opportunity_id, company_id, university_id, status,
                                    application_date, create_date, write_date)
SELECT 'LEGACY-APP-' || st.student_id, st.id, o.id, o.company_id, st.university_id,
       substring(st.student_id FROM 8), CURRENT_DATE - 90, now(), now()
  FROM internship_student st
 CROSS JOIN (SELECT id, company_id FROM internship_opportunity ORDER BY id LIMIT 1) o
 WHERE st.student_id LIKE 'LEGACY-%'
   AND NOT EXISTS (SELECT 1 FROM internship_application a WHERE a.name = 'LEGACY-APP-' || st.student_id);

-- Monitoring and completion rows for the "placed" student.
INSERT INTO internship_attendance (name, student_id, opportunity_id, attendance_date, status, active, create_date, write_date)
SELECT 'LEGACY-ATT-' || d, st.id, a.opportunity_id, CURRENT_DATE - d, 'present', TRUE, now(), now()
  FROM internship_student st
  JOIN internship_application a ON a.student_id = st.id
 CROSS JOIN generate_series(1, 3) d
 WHERE st.student_id = 'LEGACY-placed'
   AND NOT EXISTS (SELECT 1 FROM internship_attendance WHERE name = 'LEGACY-ATT-' || d);

INSERT INTO internship_performance (name, student_id, opportunity_id, review_date, score, status, active, create_date, write_date)
SELECT 'LEGACY-PERF', st.id, a.opportunity_id, CURRENT_DATE - 10, 7.5, 'good', TRUE, now(), now()
  FROM internship_student st JOIN internship_application a ON a.student_id = st.id
 WHERE st.student_id = 'LEGACY-placed' AND NOT EXISTS (SELECT 1 FROM internship_performance WHERE name = 'LEGACY-PERF');

INSERT INTO internship_meeting (name, student_id, opportunity_id, company_id, meeting_date, meeting_type, summary, active, create_date, write_date)
SELECT 'LEGACY-MEET', st.id, a.opportunity_id, a.company_id, now() - interval '5 days', 'checkin', 'Going well', TRUE, now(), now()
  FROM internship_student st JOIN internship_application a ON a.student_id = st.id
 WHERE st.student_id = 'LEGACY-placed' AND NOT EXISTS (SELECT 1 FROM internship_meeting WHERE name = 'LEGACY-MEET');

INSERT INTO internship_submission (name, student_id, opportunity_id, company_id, title, due_date, submitted_date, status, evaluation_score, active, create_date, write_date)
SELECT 'LEGACY-SUB', st.id, a.opportunity_id, a.company_id, 'Interim report', CURRENT_DATE - 3, CURRENT_DATE - 4, 'submitted', 0, TRUE, now(), now()
  FROM internship_student st JOIN internship_application a ON a.student_id = st.id
 WHERE st.student_id = 'LEGACY-placed' AND NOT EXISTS (SELECT 1 FROM internship_submission WHERE name = 'LEGACY-SUB');

INSERT INTO internship_completion (name, student_id, opportunity_id, company_id, start_date, end_date, final_report, evaluation_score, status, certificate_issued, active, create_date, write_date)
SELECT 'LEGACY-COMP', st.id, a.opportunity_id, a.company_id, CURRENT_DATE - 60, CURRENT_DATE + 30, 'Draft final report text', 65, 'in_progress', FALSE, TRUE, now(), now()
  FROM internship_student st JOIN internship_application a ON a.student_id = st.id
 WHERE st.student_id = 'LEGACY-placed' AND NOT EXISTS (SELECT 1 FROM internship_completion WHERE name = 'LEGACY-COMP');

-- Legacy internship.crm.lead rows (replaced by crm.lead in v2).
INSERT INTO internship_crm_lead (name, student_id, opportunity_id, lead_source, stage, priority, notes, active, create_date, write_date)
SELECT v.name, (SELECT id FROM internship_student ORDER BY id LIMIT 1), (SELECT id FROM internship_opportunity ORDER BY id LIMIT 1),
       v.src, v.stage, v.prio, 'Legacy lead notes', TRUE, now(), now()
  FROM (VALUES ('LEGACY-LEAD-referral', 'referral', 'qualified', '1'),
               ('LEGACY-LEAD-campus', 'campus', 'new', '0'),
               ('LEGACY-LEAD-closed', 'portal', 'closed', '0')) AS v(name, src, stage, prio)
 WHERE NOT EXISTS (SELECT 1 FROM internship_crm_lead WHERE name = v.name);

INSERT INTO internship_call_log (name, external_call_id, student_id, call_datetime, call_type, status, duration_seconds, summary, active, create_date, write_date)
SELECT 'LEGACY-CALL', 'legacy-call-1', (SELECT id FROM internship_student ORDER BY id LIMIT 1), now() - interval '1 day',
       'outbound', 'completed', 120, 'Legacy call summary', TRUE, now(), now()
 WHERE NOT EXISTS (SELECT 1 FROM internship_call_log WHERE external_call_id = 'legacy-call-1');

COMMIT;

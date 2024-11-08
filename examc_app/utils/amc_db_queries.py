# AMC sqlite connection and queries
import sqlite3
import sys
import time
import traceback
from pathlib import Path

class AMC_DB:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.conn = None
        self.cur = None
        self.connect()

    def connect(self) -> bool:
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            self.cur = self.conn.cursor()
            return True
        except sqlite3.Error as e:
            print(f"Error connecting to database: {e}")
            return False

    def close(self):
        self.conn.close()

    def execute_query(self, query):
        try:
            result = self.cur.execute(query)
            self.conn.commit()
            return result
        except sqlite3.Error as er:
            print('SQLite error: %s' % (' '.join(er.args)))
            print("Exception class is: ", er.__class__)
            print('SQLite traceback: ')
            exc_type, exc_value, exc_tb = sys.exc_info()
            print(traceback.format_exception(exc_type, exc_value, exc_tb))

def select_count_layout_pages(amc_data_path):

    db = AMC_DB(amc_data_path + "layout.sqlite")
    query_str = "SELECT count(*) FROM layout_page"
    response = db.execute_query(query_str)
    nb_pages_detected = 0;
    if response:
        nb_pages_detected = response.fetchall()[0][0]
    db.close()
    return nb_pages_detected

def select_manual_datacapture_pages(amc_data_path,amc_data_url,amc_threshold):
    db = AMC_DB(amc_data_path + "capture.sqlite")
    query_str = ("SELECT  "
                "   student as copy,"
                "   page as page, "
                "   mse as mse, "
                "   timestamp_auto, "
                "   timestamp_manual, "
                "   REPLACE(src,'%PROJET','" + amc_data_url + "') as source, "
                "   (SELECT ROUND(10*("+str(amc_threshold)+" - MIN(ABS(1.0 * cz.black / cz.total - "+str(amc_threshold)+"))) / "+str(amc_threshold)+",2) FROM capture_zone cz WHERE cz.student = cp.student AND cz.page = cp.page AND cz.total > 0 AND cz.type = 4) as sensitivity "
                "FROM capture_page cp "
                "ORDER BY copy, page")

    response = db.execute_query(query_str)
    data_pages = []
    if response:
        colname_pages = [d[0] for d in response.description]
        data_pages = [dict(zip(colname_pages, r)) for r in response.fetchall()]
    db.close()

    return data_pages

def select_manual_datacapture_questions(amc_data_path, data):

    db = AMC_DB(amc_data_path + "capture.sqlite")

    scoring_exists = False
    if Path(amc_data_path + 'scoring.sqlite').stat().st_size > 0:
        scoring_exists = True

    query_str = ("SELECT DISTINCT(id_a) as question_id ")

    if scoring_exists:
        query_str += (",sc.why as why ")


    query_str += ("   FROM capture_zone cz ")

    if scoring_exists:
        # Attach scoring db
        db.cur.execute("ATTACH DATABASE '" + amc_data_path + "scoring.sqlite' as scoring")

        query_str += ("INNER JOIN scoring.scoring_score as sc ON sc.student = " + str(data['copy']) + " AND sc.question = cz.id_a ")

    query_str += ("WHERE type = 4 "
                "AND cz.student = " + str(data['copy']) +
                " AND cz.page = " + str(data['page']))



    response = db.execute_query(query_str)
    data_questions_id = []
    if response:
        colname_questions_id = [d[0] for d in response.description]
        data_questions_id = [dict(zip(colname_questions_id, r)) for r in response.fetchall()]

    if not len(data_questions_id) > 0:
        db = AMC_DB(amc_data_path + "layout.sqlite")
        query_str = ("SELECT DISTINCT(question) as question_id, '' AS why FROM layout_box WHERE student = " + str(data['copy']) + " "
                     "AND page = " + str(data['page']) + " ORDER BY question ASC")

        response = db.execute_query(query_str)

        colname_questions_id = [d[0] for d in response.description]
        data_questions_id = [dict(zip(colname_questions_id, r)) for r in response.fetchall()]

        if not len(data_questions_id) > 0:
            return None

    db.close()

    return data_questions_id

def select_questions(amc_data_path):
    db = AMC_DB(amc_data_path + "layout.sqlite")
    query_str = ("SELECT * FROM layout_question")

    response = db.execute_query(query_str)
    data_questions = []
    if response:
        colname_questions = [d[0] for d in response.description]
        data_questions = [dict(zip(colname_questions, r)) for r in response.fetchall()]
    db.close()

    return data_questions

def select_marks_positions(amc_data_path,copy,page,seuil):

    scoring_exists = False
    if Path(amc_data_path + 'scoring.sqlite').stat().st_size > 0:
        scoring_exists = True

    db = AMC_DB(amc_data_path + "capture.sqlite")

    query_str = ("SELECT cp.zoneid, "
                 "cast(black as real) / total as bvalue,"
                 "cp.corner, "
                 "cp.x, "
                 "cp.y, "
                 "cz.manual,"
                 "cz.black ")

    if scoring_exists:
        query_str += ", sc.why "

    query_str +=  ("FROM capture_position cp "
                 "INNER JOIN capture_zone cz ON cz.zoneid = cp.zoneid ")

    if scoring_exists:
        # Attach scoring db
        db.cur.execute("ATTACH DATABASE '" + amc_data_path + "scoring.sqlite' as scoring")

        query_str += ("LEFT OUTER JOIN scoring.scoring_score sc ON sc.student = " + str(copy) + " AND sc.question = cz.id_a ")


    query_str += ("WHERE cp.zoneid in "
            "   (SELECT cz2.zoneid from capture_zone cz2 WHERE cz2.student = " + str(copy) + " AND cz2.page = " + str(page) + ") "
             "AND cp.type = 1 "
             "AND cz.type = 4 "
             "ORDER BY cp.zoneid, cp.corner ")

    response = db.execute_query(query_str)
    data_positions = []
    if response:
        colname_positions = [d[0] for d in response.description]
        data_positions = [dict(zip(colname_positions, r)) for r in response.fetchall()]
    db.close()

    return data_positions

def select_data_zones(amc_data_path, zoneid):
    db = AMC_DB(amc_data_path + "capture.sqlite")
    query_str = ("SELECT cast(black as real) / total as bvalue, * FROM capture_zone WHERE zoneid = " + str(zoneid))
    response = db.execute_query(query_str)
    colname_zones = [d[0] for d in response.description]
    data_zones = [dict(zip(colname_zones, r)) for r in response.fetchall()]
    db.close()
    return data_zones

def update_data_zone(amc_data_path, manual,zoneid, copy, page):
    db = AMC_DB(amc_data_path + "capture.sqlite")
    query_str = ("UPDATE capture_zone SET manual = " + manual + " WHERE zoneid = " + str(zoneid))
    response = db.execute_query(query_str)

    if manual != -1.0:
        timestamp_updated= int(time.time())
        query_str = ("UPDATE capture_page SET timestamp_manual = " + str(timestamp_updated) + " WHERE student = " + copy + " AND page = " + page)
        response = db.execute_query(query_str)
    db.close()
    return response

def select_nb_copies(amc_data_path):
    db = AMC_DB(amc_data_path + "capture.sqlite")
    query_str = ("SELECT COUNT(*) "
                            "FROM (SELECT student,copy "
                            "   FROM capture_page "
                            "   WHERE timestamp_auto>0 OR timestamp_manual>0)"
                            " GROUP BY student, copy")

    response = db.execute_query(query_str)
    nb_copies = 0
    if response:
        nb_copies = len(response.fetchall())
    db.close()

    return nb_copies

def select_missing_pages(amc_data_path):

    db = AMC_DB(amc_data_path + "capture.sqlite")

    # Attach layout db
    db.cur.execute("ATTACH DATABASE '" + amc_data_path + "layout.sqlite' as layout")

    query_str = ("SELECT enter.student AS student,enter.page AS page ,capture_page.copy AS copy "
                 "FROM (SELECT student,page "
                 "       FROM layout_box "
                 "       WHERE role=1 "
                 "       UNION "
                 "       SELECT student,page "
                 "       FROM layout_zone) AS enter, "
                 "       capture_page "
                 "ON enter.student=capture_page.student "
                 "EXCEPT SELECT student,page,copy FROM capture_page "
                 "ORDER BY student,copy,page")

    response = db.execute_query(query_str)
    data_missing_pages = []
    if response:
        colname_missing_pages = [d[0] for d in response.description]
        data_missing_pages = [dict(zip(colname_missing_pages, r)) for r in response.fetchall()]
    db.close()

    return data_missing_pages

def select_unrecognized_pages(amc_data_path,amc_data_url):
    db = AMC_DB(amc_data_path + "capture.sqlite")

    query_str = ("SELECT REPLACE(filename,'%PROJET','" + amc_data_url + "') as filename FROM capture_failed")

    response = db.execute_query(query_str)
    data_unrecognized_pages = []
    if response:
        colname_unrecognized_pages = [d[0] for d in response.description]
        data_unrecognized_pages = [dict(zip(colname_unrecognized_pages, r)) for r in response.fetchall()]

    data_unrecognized_pages_list = []
    db.close()

    for p in data_unrecognized_pages:
        data_unrecognized_pages_list.append({ "filename" : p["filename"].split('/')[-1], "filepath" : p["filename"]})

    return data_unrecognized_pages_list

def select_overwritten_pages(amc_data_path):
    db = AMC_DB(amc_data_path + "capture.sqlite")

    query_str = ("SELECT student,page,copy,overwritten,timestamp_auto "
                 "FROM capture_page WHERE overwritten>0 "
                 "ORDER BY student ASC, page ASC, copy ASC, timestamp_auto DESC")

    response = db.execute_query(query_str)

    data_overwritten_pages = []
    if response:
        colname_overwritten_pages = [d[0] for d in response.description]
        data_overwritten_pages = [dict(zip(colname_overwritten_pages, r)) for r in response.fetchall()]
    db.close()

    return data_overwritten_pages

def select_copy_page_zooms(amc_data_path,copy,page):
    db = AMC_DB(amc_data_path + "capture.sqlite")

    query_str = ("SELECT zoneid, "
                 "  cast(black as real) / total as bvalue, "
                 "  imagedata, "
                 "  black,"
                 "  manual "
                 "FROM capture_zone "
                 "WHERE student = "+copy+" AND page = "+page+" AND type=4")

    response = db.execute_query(query_str)

    colname_zooms = [d[0] for d in response.description]
    data_zooms = [dict(zip(colname_zooms, r)) for r in response.fetchall()]
    db.close()

    return data_zooms

def select_copy_question_page(amc_data_path,copy,question):
    db = AMC_DB(amc_data_path + "layout.sqlite")

    query_str = ("SELECT DISTINCT lb.page "
                 "FROM layout_box lb "
                 "INNER JOIN layout_question lq ON lq.question = lb.question "
                 "WHERE lb.student = " + copy + " AND lq.name = '" + question + "'")

    response = db.execute_query(query_str)

    page = response.fetchall()[0]['page']
    db.close()
    return page

def delete_unrecognized_page(amc_data_path,img_filename):
    db = AMC_DB(amc_data_path + "capture.sqlite")

    query_str = ("DELETE FROM capture_failed "
                 "WHERE filename LIKE '%"+img_filename+"'")

    response = db.execute_query(query_str)
    db.close()

def get_mean(amc_data_path):
    db = AMC_DB(amc_data_path + "scoring.sqlite")

    query_str = ("SELECT AVG(mark) as mean FROM scoring_mark")

    response = db.execute_query(query_str)
    mean = 0
    if response:
        mean = response.fetchall()[0]['mean']

    db.close()

    return mean

def get_marks(amc_data_path):
    db = AMC_DB(amc_data_path + "scoring.sqlite")

    query_str = ("SELECT student, total, max, mark FROM scoring_mark")

    response = db.execute_query(query_str)
    colname_marks = [d[0] for d in response.description]
    data_marks = [dict(zip(colname_marks, r)) for r in response.fetchall()]

    db.close()

    return data_marks
def get_questions_scoring_details(amc_data_path):
    db = AMC_DB(amc_data_path + "scoring.sqlite")
    # Attach layout db
    db.cur.execute("ATTACH DATABASE '" + amc_data_path + "layout.sqlite' as layout")

    query_str = ("SELECT sm.student as copy,sm.total, sm.max as max_total, mark, lq.name as question, ss.score, ss.max as max_question "
                 "FROM scoring_score ss "
                 "INNER JOIN layout_question lq ON lq.question = ss.question "
                 "INNER JOIN scoring_mark sm ON sm.student = ss.student "
                 "ORDER BY sm.student, lq.name")

    response = db.execute_query(query_str)
    marking_details = []
    if response:
        colname_marking = [d[0] for d in response.description]
        marking_details = [dict(zip(colname_marking, r)) for r in response.fetchall()]

    db.close()

    return marking_details

def get_count_missing_associations(amc_data_path):
    db = AMC_DB(amc_data_path + "capture.sqlite")
    db.cur.execute("ATTACH DATABASE '" + amc_data_path + "association.sqlite' as association")

    query_str = ("SELECT COUNT(*) as count FROM "
                    "(SELECT student FROM capture_page"
                    " EXCEPT SELECT student FROM association_association"
                    " WHERE manual IS NOT NULL OR auto IS NOT NULL)")

    response = db.execute_query(query_str)
    count = 0
    if response:
        count = response.fetchall()[0]['count']

    db.close()

    return count

def select_associations(amc_data_path,amc_assoc_img_path):
    db = AMC_DB(amc_data_path + "association.sqlite")
    db.cur.execute("ATTACH DATABASE '" + amc_data_path + "capture.sqlite' as capture")
    query_str = ("SELECT aa.*, '"+amc_assoc_img_path+"' || cz.image as image_path "
                 "FROM association_association aa "
                 "INNER JOIN capture_zone cz ON cz.student = aa.student "
                 "WHERE cz.type = 2")

    response = db.execute_query(query_str)
    colname_assoc = [d[0] for d in response.description]
    assoc_details = [dict(zip(colname_assoc, r)) for r in response.fetchall()]

    db.close()

    return assoc_details

def update_association(amc_data_path, copy_nr, student_id):
    db = AMC_DB(amc_data_path + "association.sqlite")
    query_str = ("UPDATE association_association "
                 "SET manual = '"+student_id+"' "
                 "WHERE student = "+copy_nr)

    response = db.execute_query(query_str)

    db.close()

    return response

def select_students_report(amc_data_path):
    db = AMC_DB(amc_data_path + "report.sqlite")
    db.cur.execute("ATTACH DATABASE '" + amc_data_path + "association.sqlite' as association")
    query_str = ("SELECT rs.student as id, coalesce(aa.auto,aa.manual) as copy, "
                 "rs.mail_status as status, rs.mail_message as error, rs.mail_timestamp as date "
                 "FROM report_student rs "
                 "INNER JOIN association_association aa "
                 "WHERE rs.student = aa.student")

    response = db.execute_query(query_str)
    colname_rep = [d[0] for d in response.description]
    rep_details = [dict(zip(colname_rep, r)) for r in response.fetchall()]

    db.close()

    return rep_details

def get_annotated_pdf_path(amc_data_path,student_id):
    db = AMC_DB(amc_data_path + "report.sqlite")
    query_str = ("SELECT file FROM report_student WHERE student = "+student_id)

    response = db.execute_query(query_str)
    file = None
    if response:
        file = response.fetchall()[0]['file']

    db.close()

    return file

def get_student_report_data(amc_data_path):
    db = AMC_DB(amc_data_path + "report.sqlite")
    query_str = ("SELECT * FROM report_student")

    response = db.execute_query(query_str)
    colname_rep = [d[0] for d in response.description]
    rep_details = [dict(zip(colname_rep, r)) for r in response.fetchall()]

    db.close()

    return rep_details

def update_report_student(amc_data_path,student,mail_timestamp,mail_status,mail_message=''):
    db = AMC_DB(amc_data_path + "report.sqlite")
    query_str = ("UPDATE report_student "
                 "SET mail_status = "+str(mail_status)+", "
                 "mail_timestamp = "+str(int(mail_timestamp))+", "
                 "mail_message = '"+mail_message.replace("'","''") + "' "
                 "WHERE student = " + student)

    response = db.execute_query(query_str)

    db.close()

    return response

def get_questions(amc_data_path):
    db = AMC_DB(amc_data_path + "layout.sqlite")
    query_str = "SELECT * FROM layout_question"
    response = db.execute_query(query_str)
    colname_question = [d[0] for d in response.description]
    question_details = [dict(zip(colname_question, r)) for r in response.fetchall()]

    return question_details

def get_question_start_page_by_student(amc_data_path,question_name,student_id):
    db = AMC_DB(amc_data_path + "layout.sqlite")
    query_str = ("SELECT DISTINCT b.student, q.question, q.name, b.page FROM layout_box b"
                 " INNER JOIN layout_question q ON q.question = b.question"
                 " WHERE q.name = '"+ str(question_name) + "' AND b.student = " + str(student_id))

    response = db.execute_query(query_str)
    colname_qp = [d[0] for d in response.description]
    qp_details = [dict(zip(colname_qp, r)) for r in response.fetchall()]

    return qp_details

def select_capture_pages(amc_data_path):
    db = AMC_DB(amc_data_path + "capture.sqlite")
    query_str = ("SELECT student, page, src FROM capture_page ORDER BY student, page")

    response = db.execute_query(query_str)
    colname_cp = [d[0] for d in response.description]
    cp_details = [dict(zip(colname_cp, r)) for r in response.fetchall()]

    return cp_details

def update_capture_page_src(amc_data_path,student,page,new_filename):
    db = AMC_DB(amc_data_path + "capture.sqlite")
    query_str = ("UPDATE capture_page SET src = '"+new_filename+"' WHERE student = "+str(student)+" AND page = "+str(page))
    response = db.execute_query(query_str)

    return response
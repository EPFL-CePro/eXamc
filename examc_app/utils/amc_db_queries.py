# AMC sqlite connection and queries
import sqlite3
import sys
import traceback
import time


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
                "   (SELECT ROUND(10*("+str(amc_threshold)+" - MIN(ABS(1.0 * cz.black / cz.total - "+str(amc_threshold)+"))) / "+str(amc_threshold)+",2) FROM capture_zone cz WHERE cz.student = cp.student AND cz.page = cp.page) as sensitivity "
                "FROM capture_page cp "
                "ORDER BY copy, page")

    response = db.execute_query(query_str)

    colname_pages = [d[0] for d in response.description]
    data_pages = [dict(zip(colname_pages, r)) for r in response.fetchall()]
    db.close()
    return data_pages

def select_manual_datacapture_questions(amc_data_path, data):

    db = AMC_DB(amc_data_path + "capture.sqlite")

    # Attach scoring db
    db.cur.execute("ATTACH DATABASE '" + amc_data_path + "scoring.sqlite' as scoring")

    query_str = ("SELECT DISTINCT(id_a) as question_id, "
                "   sc.why as why "
                "   FROM capture_zone cz "
                "   INNER JOIN scoring.scoring_score as sc ON sc.student = " + str(data['copy']) + " AND sc.question = cz.id_a "
                "WHERE type = 4 "
                "AND cz.student = " + str(data['copy']) +
                " AND cz.page = " + str(data['page']))



    response = db.execute_query(query_str)

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

    colname_questions = [d[0] for d in response.description]
    data_questions = [dict(zip(colname_questions, r)) for r in response.fetchall()]
    db.close()

    return data_questions

def select_marks_positions(amc_data_path,copy,page):

    db = AMC_DB(amc_data_path + "capture.sqlite")

    # Attach scoring db
    db.cur.execute("ATTACH DATABASE '" + amc_data_path + "scoring.sqlite' as scoring")

    query_str = ("SELECT cp.zoneid, "
                "cp.corner, "
                "cp.x, "
                "cp.y, "
                "cz.manual,"
                "cz.black, "
                "sc.why "
                "FROM capture_position cp "
                "INNER JOIN capture_zone cz ON cz.zoneid = cp.zoneid "
                "LEFT OUTER JOIN scoring.scoring_score sc ON sc.student = " + str(copy) + " AND sc.question = cz.id_a "
                "WHERE cp.zoneid in "
                "   (SELECT cz2.zoneid from capture_zone cz2 WHERE cz2.student = " + str(copy) + " AND cz2.page = " + str(page) + ") "
                 "AND cp.type = 1 "
                 "AND cz.type = 4 "
                 "ORDER BY cp.zoneid, cp.corner ")

    response = db.execute_query(query_str)
    colname_positions = [d[0] for d in response.description]
    data_positions = [dict(zip(colname_positions, r)) for r in response.fetchall()]
    db.close()

    return data_positions

def select_data_zones(amc_data_path, zoneid):
    db = AMC_DB(amc_data_path + "capture.sqlite")
    query_str = ("SELECT * FROM capture_zone WHERE zoneid = " + str(zoneid))
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
                 "       FROM layout_namefield) AS enter, "
                 "       capture_page "
                 "ON enter.student=capture_page.student "
                 "EXCEPT SELECT student,page,copy FROM capture_page "
                 "ORDER BY student,copy,page")

    response = db.execute_query(query_str)

    colname_missing_pages = [d[0] for d in response.description]
    data_missing_pages = [dict(zip(colname_missing_pages, r)) for r in response.fetchall()]
    db.close()

    return data_missing_pages

def select_unrecognized_pages(amc_data_path,amc_data_url):
    db = AMC_DB(amc_data_path + "capture.sqlite")

    query_str = ("SELECT REPLACE(filename,'%PROJET','" + amc_data_url + "') as filename FROM capture_failed")

    response = db.execute_query(query_str)

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

    query_str = ("SELECT sm.student,sm.total, sm.max as max_total, mark, lq.name, sq.score, sq.max as max_question "
                 "FROM scoring_score sq "
                 "INNER JOIN layout_question lq ON lq.question = lq.question "
                 "INNER JOIN scoring_mark sm ON sm.student = sq.student "
                 "ORDER BY sm.student, lq.name")

    response = db.execute_query(query_str)
    colname_marking = [d[0] for d in response.description]
    marking_details = [dict(zip(colname_marking, r)) for r in response.fetchall()]

    db.close()

    return marking_details
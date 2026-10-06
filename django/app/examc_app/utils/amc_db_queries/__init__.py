import logging
import sqlite3

from examc_app.services.amc.AmcDb import AmcDb

logger = logging.getLogger(__name__)

def select_count_layout_pages(amc_data_path: str):
    db = AmcDb(amc_data_path + "layout.sqlite")
    query_str = "SELECT count(*) FROM layout_page"
    response = db.execute_query(query_str)
    nb_pages_detected = 0

    if response: nb_pages_detected = response.fetchall()[0][0]

    db.close()
    return nb_pages_detected


def select_questions(amc_data_path):
    db = AmcDb(amc_data_path + "layout.sqlite")
    query_str = ("SELECT * FROM layout_question")

    response = db.execute_query(query_str)
    data_questions = []
    if response:
        colname_questions = [d[0] for d in response.description]
        data_questions = [dict(zip(colname_questions, r)) for r in response.fetchall()]
    db.close()

    return data_questions



def select_copy_question_page(amc_data_path: str, copy: str, question: str):
    db = AmcDb(amc_data_path + "layout.sqlite")

    query_str = (
        "SELECT DISTINCT lb.page "
        "FROM layout_box lb "
        "INNER JOIN layout_question lq ON lq.question = lb.question "
        "WHERE lb.student = :copy AND lq.name = ':question'"
    )

    cursor = db.execute_query(query_str, {"copy": copy, "question": question})
    if not cursor: return None

    data = cursor.fetchall()

    page = None
    if data[0] and data[0]['page']: page = data[0]['page']

    db.close()

    return page


def get_mean(amc_data_path: str):
    db = AmcDb(amc_data_path + "scoring.sqlite")

    query_str = "SELECT AVG(mark) as mean FROM scoring_mark"

    response = db.execute_query(query_str)
    row = response.fetchone() if response else None
    mean = 0
    if row and row['mean'] is not None:
        mean = round(row['mean'], 4)

    db.close()

    return mean


def get_marks(amc_data_path):
    db = AmcDb(amc_data_path + "scoring.sqlite")

    query_str = "SELECT student, total, max, mark FROM scoring_mark"

    response = db.execute_query(query_str)
    colname_marks = [d[0] for d in response.description]
    data_marks = [dict(zip(colname_marks, r)) for r in response.fetchall()]

    db.close()

    return data_marks


def get_questions_scoring_details(amc_data_path):
    db = AmcDb(amc_data_path + "scoring.sqlite")
    # Attach layout db
    db.cursor.execute("ATTACH DATABASE '" + amc_data_path + "layout.sqlite' as layout")

    query_str = (
        "SELECT sm.student as copy,sm.total, sm.max as max_total, mark, lq.name as question, ss.score, ss.max as max_question "
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

def select_students_report(amc_data_path):
    db = AmcDb(amc_data_path + "report.sqlite")
    db.cursor.execute("ATTACH DATABASE '" + amc_data_path + "association.sqlite' as association")
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


def get_annotated_pdf_path(amc_data_path, student_id):
    db = AmcDb(amc_data_path + "report.sqlite")
    query_str = ("SELECT file FROM report_student WHERE student = " + student_id)

    response = db.execute_query(query_str)
    file = None
    if response:
        file = response.fetchall()[0]['file']

    db.close()

    return file


def get_student_report_data(amc_data_path):
    db = AmcDb(amc_data_path + "report.sqlite")
    try:
        db.cursor.execute("ATTACH DATABASE '" + amc_data_path + "association.sqlite' as association")
        query_str = (
            "SELECT rs.*, "
            "aa.student AS amc_copy, "
            "COALESCE(NULLIF(aa.manual, ''), NULLIF(aa.auto, '')) AS associated_student "
            "FROM report_student rs "
            "LEFT JOIN association.association_association aa ON aa.student = rs.student"
        )
        response = db.execute_query(query_str)
    except sqlite3.Error:
        response = None

    if not response:
        query_str = "SELECT rs.*, rs.student AS amc_copy, NULL AS associated_student FROM report_student rs"
        response = db.execute_query(query_str)

    colname_rep = [d[0] for d in response.description]
    rep_details = [dict(zip(colname_rep, r)) for r in response.fetchall()]

    db.close()

    return rep_details


def update_report_student(amc_data_path, student, mail_timestamp, mail_status, mail_message=''):
    db = AmcDb(amc_data_path + "report.sqlite")
    query_str = ("UPDATE report_student "
                 "SET mail_status = " + str(mail_status) + ", "
                                                           "mail_timestamp = " + str(int(mail_timestamp)) + ", "
                                                                                                            "mail_message = '" + mail_message.replace(
        "'", "''") + "' "
                     "WHERE student = " + student)

    response = db.execute_query(query_str)

    db.close()

    return response


def get_questions(amc_data_path):
    db = AmcDb(amc_data_path + "layout.sqlite")
    query_str = "SELECT * FROM layout_question"
    response = db.execute_query(query_str)
    colname_question = [d[0] for d in response.description]
    question_details = [dict(zip(colname_question, r)) for r in response.fetchall()]

    return question_details


def get_question_start_page_by_student(amc_data_path, question_name, student_id):
    db = AmcDb(amc_data_path + "layout.sqlite")
    query_str = ("SELECT DISTINCT b.student, q.question, q.name, b.page FROM layout_box b"
                 " INNER JOIN layout_question q ON q.question = b.question"
                 " WHERE q.name = '" + str(question_name) + "' AND b.student = " + str(student_id))

    response = db.execute_query(query_str)
    colname_qp = [d[0] for d in response.description]
    qp_details = [dict(zip(colname_qp, r)) for r in response.fetchall()]

    return qp_details


def get_question_name_by_student_page(amc_data_path, student_id, page_no):
    db = AmcDb(amc_data_path + "layout.sqlite")
    query_str = ("SELECT DISTINCT q.name FROM layout_box b"
                 " INNER JOIN layout_question q ON q.question = b.question"
                 " WHERE b.page = " + str(page_no) + " AND b.student = " + str(student_id))

    response = db.execute_query(query_str)
    rows = response.fetchall()
    if rows:
        qname = rows[0]['name']
    else:
        qname = get_question_name_by_student_page(amc_data_path, student_id, page_no - 1)
    return qname



def get_question_max_points(amc_data_path, question_name, copy_nr):
    db = AmcDb(amc_data_path + "scoring.sqlite")
    db.cursor.execute("ATTACH DATABASE '" + amc_data_path + "layout.sqlite' as layout")
    query_str = ("SELECT strategy FROM scoring_question sc"
                 " INNER JOIN layout_question lq ON lq.question = sc.question"
                 " WHERE lq.name = '" + str(question_name) + "'")

    if copy_nr:
        query_str += " AND sc.student = " + str(copy_nr)

    response = db.execute_query(query_str)
    strategy = response.fetchall()[0]['strategy']
    max_points = strategy.split("=")[1]
    return max_points


def get_question_number(amc_data_path, copy_nr, question_name):
    db = AmcDb(amc_data_path + "layout.sqlite")

    # minimal safe quoting
    qname = question_name.replace("'", "''")  # SQLite escaping

    query_str = f"""
    WITH q AS (
      SELECT question
      FROM layout_question
      WHERE name = '{qname}'
    ),
    firstpos AS (
      SELECT b.question,
             MIN(b.page) AS p,
             MIN(b.ymin) AS y0,
             MIN(b.xmin) AS x0
      FROM layout_box b
      WHERE b.student = {int(copy_nr)}
        AND b.role = 1
      GROUP BY b.question
    ),
    ordered AS (
      SELECT question,
             ROW_NUMBER() OVER (ORDER BY p, y0, x0) AS qnum
      FROM firstpos
    )
    SELECT o.qnum
    FROM ordered o
    JOIN q USING(question);
    """

    response = db.execute_query(query_str)
    row = response.fetchone()
    db.close()

    if row is None:
        raise ValueError(f"Question name '{question_name}' not found for student/copy {copy_nr}")

    return row["qnum"]


################################################
# AMC CONVERT
################################################

def get_page_layout_boxes(amc_data_path, student, page_nr):
    db = AmcDb(amc_data_path + "layout.sqlite")
    query_str = (
            "SELECT * FROM layout_box WHERE student = " + student + " AND page = " + page_nr + " ORDER BY question, answer")

    response = db.execute_query(query_str)
    colname_layout_boxes = [d[0] for d in response.description]
    layout_boxes_details = [dict(zip(colname_layout_boxes, r)) for r in response.fetchall()]

    return layout_boxes_details

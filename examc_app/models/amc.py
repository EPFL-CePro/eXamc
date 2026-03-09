#############################
# AMC MODELS
#############################

# ### LAYOUT
#
# class LayoutVariables(models.Model):
#     """
#     Corresponds to table layout_variables:
#       name TEXT UNIQUE
#       value TEXT
#     """
#     name = models.CharField(max_length=255, unique=True)
#     value = models.CharField(max_length=255)
#
# class LayoutMark(models.Model):
#     """
#     Corresponds to table layout_mark:
#       student INTEGER
#       page INTEGER
#       corner INTEGER
#       x REAL
#       y REAL
#       PRIMARY KEY (student,page,corner)
#     Again, emulate with unique_together.
#     """
#     student = models.IntegerField()
#     page = models.IntegerField()
#     corner = models.IntegerField()
#     x = models.FloatField()
#     y = models.FloatField()
#
#     class Meta:
#         unique_together = (('student', 'page', 'corner'),)
#
#
# class LayoutBox(models.Model):
#     """
#     Corresponds to table layout_box:
#       student INTEGER
#       page INTEGER
#       role INTEGER DEFAULT 1
#       question INTEGER
#       answer INTEGER
#       xmin REAL
#       xmax REAL
#       ymin REAL
#       ymax REAL
#       flags INTEGER DEFAULT 0
#       char TEXT
#       PRIMARY KEY (student, role, question, answer)
#       Index: layout_index_box_studentpage ON (student, page, role)
#     """
#     student = models.IntegerField()
#     page = models.IntegerField()
#     role = models.IntegerField(default=1)
#     question = models.IntegerField()
#     answer = models.IntegerField()
#     xmin = models.FloatField(null=True, blank=True)
#     xmax = models.FloatField(null=True, blank=True)
#     ymin = models.FloatField(null=True, blank=True)
#     ymax = models.FloatField(null=True, blank=True)
#     flags = models.IntegerField(default=0)
#     char = models.CharField(max_length=255, blank=True, null=True)
#
#     class Meta:
#         unique_together = (('student', 'role', 'question', 'answer'),)
#         indexes = [
#             models.Index(fields=['student', 'page', 'role'],
#                          name='layout_index_box_studentpage'),
#         ]
#
#
# class LayoutDigit(models.Model):
#     """
#     Corresponds to table layout_digit:
#       student INTEGER
#       page INTEGER
#       numberid INTEGER
#       digitid INTEGER
#       xmin REAL
#       xmax REAL
#       ymin REAL
#       ymax REAL
#       PRIMARY KEY (student,page,numberid,digitid)
#     """
#     student = models.IntegerField()
#     page = models.IntegerField()
#     numberid = models.IntegerField()
#     digitid = models.IntegerField()
#     xmin = models.FloatField(null=True, blank=True)
#     xmax = models.FloatField(null=True, blank=True)
#     ymin = models.FloatField(null=True, blank=True)
#     ymax = models.FloatField(null=True, blank=True)
#
#     class Meta:
#         unique_together = (('student', 'page', 'numberid', 'digitid'),)
#
# class LayoutPage(models.Model):
#     """
#     Corresponds to table layout_page:
#       student INTEGER
#       page INTEGER
#       checksum INTEGER
#       sourceid INTEGER
#       subjectpage INTEGER
#       dpi REAL
#       width REAL
#       height REAL
#       markdiameter REAL
#       PRIMARY KEY (student,page)
#     We emulate the primary key using unique_together below.
#     """
#     student = models.IntegerField()
#     page = models.IntegerField()
#     checksum = models.IntegerField(null=True, blank=True)
#     subjectpage = models.IntegerField(null=True, blank=True)
#     dpi = models.FloatField(null=True, blank=True)
#     width = models.FloatField(null=True, blank=True)
#     height = models.FloatField(null=True, blank=True)
#     markdiameter = models.FloatField(null=True, blank=True)
#
#     class Meta:
#         unique_together = (('student', 'page'),)
#
# class LayoutQuestion(models.Model):
#     """
#     Corresponds to table layout_question:
#       question INTEGER PRIMARY KEY
#       name TEXT
#     We'll use question as the primary key.
#     """
#     question = models.IntegerField(primary_key=True)
#     name = models.CharField(max_length=255, blank=True,null=True)
#
#
# class LayoutAssociation(models.Model):
#     """
#     Corresponds to table layout_association:
#       student INTEGER PRIMARY KEY
#       id TEXT
#       filename TEXT
#     'id' conflicts with Django's auto 'id', so rename to association_id.
#     We keep 'student' as the primary_key, matching the SQL schema.
#     """
#     student = models.IntegerField(primary_key=True)
#     association_id = models.TextField(db_column='id', null=True, blank=True)
#     filename = models.CharField(max_length=255, blank=True,null=True)
#
#
# class LayoutChar(models.Model):
#     """
#     Corresponds to table layout_char:
#       question INTEGER
#       answer INTEGER
#       char TEXT
#       Unique index on (question, answer)
#     """
#     question = models.IntegerField()
#     answer = models.IntegerField()
#     char = models.CharField(max_length=255, blank=True,null=True)
#
#     class Meta:
#         unique_together = (('question', 'answer'),)
#
#
# class LayoutZone(models.Model):
#     """
#     Corresponds to table layout_zone:
#       student INTEGER
#       page INTEGER
#       zone TEXT
#       flags INTEGER DEFAULT 0
#       xmin REAL
#       xmax REAL
#       ymin REAL
#       ymax REAL
#       Index: layout_index_zone ON (student,page)
#     There is no PRIMARY KEY definition. By default, Django adds its own 'id'.
#     """
#     student = models.IntegerField()
#     page = models.IntegerField()
#     zone = models.CharField(max_length=255, blank=True,null=True)
#     flags = models.IntegerField(default=0)
#     xmin = models.FloatField(null=True, blank=True)
#     xmax = models.FloatField(null=True, blank=True)
#     ymin = models.FloatField(null=True, blank=True)
#     ymax = models.FloatField(null=True, blank=True)
#
#     class Meta:
#         indexes = [
#             models.Index(fields=['student', 'page'], name='layout_index_zone'),
#         ]


import logging
import sqlite3
from config import *


class SpeedDB(object):
	def __init__(self, dbpath):
		self.dbpath=dbpath
		self._dbinit
		self.cfg=Config()
		
	def _dbinit(self):
		db_conn = self.db_check(self.dbpath)
		# check and open sqlite3 db
		if db_conn is not None:
			db_conn = self.db_open(self.dbpath)
			if db_conn is None:
				logging.error("Failed: Connect to sqlite3 DB %s", self.dbpath)
				db_is_open = False
			else:
				logging.info("sqlite3 DB is Open %s", self.dbpath)
				db_cur = db_conn.cursor()  # Set cursor position
				db_is_open = True

		# insert status column into speed table.  Can be used for
		# alpr (automatic license plate reader) processing to indicate
		# images to be processed eg null field entry.
		try:
			db_conn.execute('alter table speed add status text')
			db_conn.execute('alter table speed add cam_location text')
		except sqlite3.OperationalError:
			pass
		db_conn.close()

	def _isSQLite3(self,filename):
		"""
		Determine if filename is in sqlite3 format
		"""
		if os.path.isfile(filename):
			if os.path.getsize(filename) < 100: # SQLite database file header is 100 bytes
				size = os.path.getsize(filename)
				logging.error("%s %d is Less than 100 bytes", filename, size)
				return False
			with open(filename, 'rb') as fd:
				header = fd.read(100)
				if header.startswith(b'SQLite format 3'):
					logging.info("Success: File is sqlite3 Format %s", filename)
					return True
				else:
					logging.error("Failed: File NOT sqlite3 Header Format %s", filename)
					return False
		else:
			logging.warning("File Not Found %s", filename)
			logging.info("Create sqlite3 database File %s", filename)
			try:
				conn = sqlite3.connect(filename)
			except sqlite3.Error as e:
				logging.error("Failed: Create Database %s.", filename)
				logging.error("Error Msg: %s", e)
				return False
			conn.commit()
			conn.close()
			logging.info("Success: Created sqlite3 Database %s", filename)
			return True

	def db_check(self,db_file):
		"""
		Check if db_file is a sqlite3 file and connect if possible
		"""
		if self._isSQLite3(db_file):
			try:
				conn = sqlite3.connect(db_file, timeout=1)
			except sqlite3.Error as e:
				logging.error("Failed: sqlite3 Connect to DB %s", db_file)
				logging.error("Error Msg: %s", e)
				return None
		else:
			logging.error("Failed: sqlite3 Not DB Format %s", db_file)
			return None
		conn.commit()
		logging.info("Success: sqlite3 Connected to DB %s", db_file)
		return conn

	def db_open(self,db_file):
		"""
		Insert speed data into database table
		"""
		try:
			db_conn = sqlite3.connect(db_file)
			cursor = db_conn.cursor()
		except sqlite3.Error as e:
			logging.error("Failed: sqlite3 Connect to DB %s", db_file)
			logging.error("Error Msg: %s", e)
			return None

		sql_cmd = '''create table if not exists {} (idx text primary key,
					log_timestamp text,
					camera text,
					ave_speed real, speed_units text, image_path text,
					image_w integer, image_h integer, image_bigger integer,
					direction text, plugin_name text,
					cx integer, cy integer,
					mw integer, mh integer, m_area integer,
					x_left integer, x_right integer,
					y_upper integer, y_lower integer,
					max_speed_over integer,
					min_area integer, track_counter integer,
					cal_obj_px integer, cal_obj_mm integer, status text, cam_location text)'''.format(self.cfg.DB_TABLE)
		try:
			db_conn.execute(sql_cmd)
		except sqlite3.Error as e:
			logging.error("Failed: To Create Table %s on sqlite3 DB %s", self.cfg.DB_TABLE, db_file)
			logging.error("Error Msg: %s", e)
			return None
		else:
			db_conn.commit()
		return db_conn

	def db_add_record(self,sql_cmd):
		""" Insert speed_data into sqlite3 database table"""
		#Note cam_location and status may not be in proper order unless speed table is recreated.
		try:
			self.speed_db.db_add_record(sql_cmd)
			db_conn = self.db_check(self.dbpath)
			db_conn.execute(sql_cmd)
			db_conn.commit()
			db_conn.close()
		except sqlite3.Error as e:
				logging.error("sqlite3 DB %s", self.dbpath)
				logging.error("Failed: To INSERT Speed Data into TABLE %s", self.cfg.DB_TABLE)
				logging.error("Err Msg: %s", e)
		else:
				logging.info(" SQL - Inserted Data Row into %s", self.dbpath)


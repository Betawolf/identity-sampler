import os
import csv

try:
  import common.logger
except ImportError as ie:
  from sys import path
  path.append(os.path.abspath('.'))
  path.append(os.path.abspath('..'))
  import common.logger


class ProfileStore:
  
  fieldnames = ['uid','network','network_id','url','search_term']
  matchfieldnames = ['from','to']
  

  def __init__(self, filename, logger=None):
    self.matchfile = 'matches-'+filename
    self.records = []
    self.matches = {}
    self.curuid = 0
    if not logger:
      logger = common.logger.getLogger('profile_store')
    self.logger = logger
    if os.path.exists(filename):
      reader = csv.DictReader(open(filename,'r'),self.fieldnames)
      for row in reader:
        self.records.append(row)
        self.curuid = int(row['uid'])
    if os.path.exists(self.matchfile):
      reader = csv.DictReader(open(self.matchfile,'r'),self.matchfieldnames)
      for row in reader:
        uidfrom = row['from']
        uidto = row['to']
        if uidfrom not in self.matches:
           self.matches[uidfrom] = []
        if uidto not in self.matches[uidfrom]:
            self.matches[uidfrom].append(uidto)
    self.outputwriter = csv.DictWriter(open(filename,'a'),self.fieldnames)
    self.matchoutputwriter = csv.DictWriter(open(self.matchfile,'a'),self.matchfieldnames)
    self.logger.info("Initialised ProfileStore, curid={}".format(self.curuid))
     

  def add_match(self, uidfrom, uidto):
    """ Add a mapping between two recorded profiles. """
    known_ids = 0
    for r in self.records:
      if r['uid'] in [uidfrom,uidto]:
        known_ids += 1
    if known_ids == 2:
      if uidfrom not in self.matches:
         self.matches[uidfrom] = []
      if uidto not in self.matches[uidfrom]:
          self.matches[uidfrom].append(uidto)
          self.matchoutputwriter.writerow({'from':uidfrom, 'to':uidto})
      else:
          self.logger.info("Pair ({}, {}) is not new, ignoring.".format(uidfrom, uidto))
    else:
      self.logger.warn("Submitted match ({},{}) had {} uids not on record.".format(uidfrom, uidto, 2-known_ids))


  def is_matched(self, uid):
    """ Check if a UID is a known match."""
    if uid in self.matches:
      return True
    else:
      for kid in self.matches:
        if uid in self.matches[kid]:
          return True
    return False

  def is_match(self, uidfrom, uidto):
    if uidfrom in self.matches:
      return uidto in self.matches[uidfrom]
    elif uidto in self.matches:
      return uidfrom in self.matches[uidto]
    return False
    

  def add_record(self, record):
    """ Add a profile to the record. Checks is_new. 
    Returns the unique ID assigned to the record. """
    match = self.get_match(record)
    if not match:
      self.curuid += 1
      record['uid'] = self.curuid
      self.records.append(record)
      self.outputwriter.writerow(record)
    else:
      self.logger.info("Record `{}` is not new, ignoring.".format(record['network_id']))
      return match['uid']
    return self.curuid


  def get_match(self, record):
    """ Check an added record would be new. """
    for rec in self.records:
      if rec['network_id'] == record['network_id'] and rec['network'] == record['network']:
        return rec
    return None

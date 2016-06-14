import argparse
import common.profilestore
import common.logger
import shutil
import os
import pickle

def merge(runnames, outname):
  dup_count = 0
  missing_count = 0
  recount = 0
  iterum = 0
  logger = common.logger.getLogger('merger',output='merge.log',level='info')
  dstdir = outname+'-profiles'
  if not os.path.exists(dstdir):
    os.mkdir(dstdir)
  dstps = common.profilestore.ProfileStore(outname+'-db.csv', logger)
  for name in runnames:
    ps = common.profilestore.ProfileStore(name+'-db.csv')
    srcdir = name+'-profiles'
    iterum = dstps.curuid
    for record in ps.records:
      uid = int(record['uid'])
      fname = str(uid)+'.pickle'
      if not os.path.exists(srcdir+os.sep+fname):
        logger.warn("Record {} in '{}' does not have a file.".format(uid, name))
        missing_count += 1
      else:
        tmp = int(dstps.add_record(record))
        if tmp <= recount:
          logger.warn("Record {} in '{}' is not new.".format(uid, name))
          dup_count += 1
        recount = tmp
        shutil.copyfile(srcdir+os.sep+fname, dstdir+os.sep+fname)
    for fromuid in ps.matches:
      for touid in ps.matches[fromuid]:
        dstps.add_match((iterum+int(fromuid)), (iterum+int(touid)))
  print('Total of {} records copied. {} duplicates were discarded. {} records had no corresponding file.'.format(dstps.curuid, dup_count, missing_count))


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Merge two or more samples into one, removing duplicate profiles.')
  parser.add_argument('output_name', help='The identifier to use for the output ProfileStore.')
  parser.add_argument('run_names', help='A list of identifiers for the existing samples to merge.', nargs='+')
  args = parser.parse_args()

  merge(args.run_names, args.output_name)

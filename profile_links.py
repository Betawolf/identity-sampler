import argparse
import pickle
import os
import common.analyser
import common.profilestore


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Extract the links from G+ profiles field')
  parser.add_argument('db', help='A database file.')
  args = parser.parse_args()

  logger = common.logger.getLogger('link-extractor',output='link.log',level='info')

  ps = common.profilestore.ProfileStore(args.db,logger=logger)
  
  dirname = args.db[:-7].replace('-','')
  profdir = dirname+'-profiles'
  linksfile = dirname+'-links.txt'
  lfh = open(linksfile,'w')

  for record in ps.records:
    if record['network'] == 'Google+':
      fname = profdir+os.sep+record['uid']+'.pickle'
      try:
        p = pickle.load(open(fname,'rb'))
        for l in p.profile_links:
          lfh.write("{}\n".format(l))
      except Exception as e:
        print(e)
    

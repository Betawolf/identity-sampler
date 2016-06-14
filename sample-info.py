import argparse
import math
import pickle
import os
import common.analyser
import common.profilestore


def mean(l):
  if len(l) == 0:
    return 0
  return sum(l)/len(l)

def sd(l):
  if len(l) == 0:
    return 0
  m = mean(l)
  ssd = sum([(i - m)**2 for i in l])
  v = ssd/len(l)
  return math.sqrt(v)


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Extract the personal names of a set of results.')
  parser.add_argument('db', help='A database file.')
  args = parser.parse_args()

  logger = common.logger.getLogger('measures-extractor',output='measures.log',level='info')

  ps = common.profilestore.ProfileStore(args.db,logger=logger)
  
  dirname = args.db[:-7].replace('-','')
  profdir = dirname+'-profiles'

  
  measures = ['Age','NumFollowers','NumFollowing','NumInteracted','NumLocations','NumTexts','NumDescribes','NumLinks','NumPics','NumTimes','Matched']
  networks = {}
  for network in ['Google+','Twitter']:
    networks[network] = {}
    for measure in measures:
      networks[network][measure] = []
   
  for record in ps.records:
      fname = profdir+os.sep+record['uid']+'.pickle'
      try:
        p = pickle.load(open(fname,'rb'))
      except FileNotFoundError as fnf:
        print("File Not Found: {}".format(fname))
        continue
      name = p.bestname() 
      matched = 0
      if record['uid'] in ps.matches:
        matched = 1
      else:
        for m in ps.matches:
          if record['uid'] in ps.matches[m]:
            matched = 1
            break
      if name:
        name = name.replace(',',' ')
      occ = p.occupation
      if occ:
        occ = occ.replace(',',' ')
        occ = occ.replace('\n',' & ')
      
      texts = [c for c in p.content if c.ctype == common.analyser.Content.TEXT]
      stats = networks[p.network]
      stats['Age'].append(p.age)
      stats['NumFollowers'].append(max([p.subscribers,len(p.followers)]))
      stats['NumFollowing'].append(max([p.subscribed, len(p.followed_by)]))
      stats['NumInteracted'].append(len(p.interacted))
      stats['NumLocations'].append(len(p.location_set))
      stats['NumTexts'].append(len(texts))
      stats['NumDescribes'].append(len(p.self_descriptions))
      stats['NumLinks'].append(len(p.getLinks()))
      stats['NumPics'].append(len(p.profile_images))
      stats['NumTimes'].append(len(p.activity_timestamps))
      stats['Matched'].append(matched)

  for network in networks:
    fn = '{}-{}.csv'.format(dirname,network)
    fh = open(fn,'w')
    nf = networks[network]
    
    #Write header
    fh.write('Row')
    for measure in measures:
      fh.write(',')
      fh.write(measure)
    fh.write('\n')

    #Write data
    for i in range(0,len(nf[measures[0]])):
      fh.write(str(i))
      for measure in measures:
        fh.write(',')
        level = networks[network][measure][i]
        fh.write(str(level))
      fh.write('\n')

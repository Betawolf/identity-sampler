import argparse

import common.sampler
import common.logger
import common.connect

import gplus.connect
import facebook.connect
import twitter.connect
import linkedin.connect

import gplus.search
import facebook.search
import twitter.search
import linkedin.search

import gplus.downloader
import facebook.downloader
import twitter.downloader
import linkedin.downloader

import gplus.analyser
import facebook.analyser
import twitter.analyser
import linkedin.analyser


parser = argparse.ArgumentParser(description='Sample profiles linked from Google+.')
parser.add_argument('run_name', help='The name to use for the run and its output files.')
parser.add_argument('n', type=int, help='The number of uncommon surnames to sample. Cannot be more than {} (and should not usually be close to that number).'.format(common.sampler.maxlen))
parser.add_argument('--gk', help='The keyfile containing one or more Google+ access keys.')
parser.add_argument('--fk', help='The keyfile containing one or more Facebook access keys.')
parser.add_argument('--tk', help='The keyfile containing one or more Twitter access key sets.')
parser.add_argument('--lk', help='The keyfile containing one or more LinkedIn access key sets.')
parser

args = parser.parse_args()


#Initialise logger
logger = common.logger.getLogger('sampling-tool', output=args.run_name+'.log', level='info')
logger.info('Logger initialised.')

#Prime connection handlers.
gpconn = None
fbconn = None
twconn = None
liconn = None
if args.gk:
  gpconn = common.connect.PooledConnection(args.gk, gplus.connect.GoogleConnection, logger)
if args.fk:
  fbconn = common.connect.PooledConnection(args.fk, facebook.connect.FacebookConnection, logger)
if args.tk:
  twconn = common.connect.PooledConnection(args.tk, twitter.connect.TwitterConnection, logger)
if args.lk:
  liconn = common.connect.PooledConnection(args.lk, linkedin.connect.LinkedInConnection, logger)

if not gpconn:
  print("Cannot continue without at least a valid Google+ access key.")
  exit()

# Select seed surnames from known uncommon surnames.
sample_file = args.run_name+'-seed_surnames.txt'
logger.info('Sampling into {}'.format(sample_file))
common.sampler.sample(common.sampler.datafile, sample_file, common.sampler.maxlen, args.n)

#Initialise centralised store
db_file = args.run_name+'-db.csv'
logger.info('Database is {}'.format(db_file))
profilestore = common.profilestore.ProfileStore(db_file, logger)

# Initialise Google+ search handler
gplussearch = gplus.search.GPlusSearch(gpconn, profilestore, logger)

#Execute initial surname-based search
gplussearch.search_all(sample_file)

#Download the resultant items.
raw_dir = args.run_name+'-raw'
profile_dir = args.run_name+'-profiles'
gplusdown = gplus.downloader.GplusDownloader(profilestore, gpconn, logger)
gplusdown.run(dirpath=raw_dir)

#Analyse the downloaded profiles, pulling out matches and names for negative example sampling.
namesfile = args.run_name+'-names.txt'
gplusanal = gplus.analyser.GplusAnalyser(profilestore, logger=logger, namesfile=namesfile)
gplusanal.run(indirpath=raw_dir, outdirpath=profile_dir)

#Now do searches to get negative examples and download all data.
if twconn:
  logger.info("Running Twitter Negative Search.")
  #Search
  twsearch = twitter.search.TwitterSearch(twconn, profilestore, logger)
  twsearch.search_all(namesfile)
  #Download
  twdown = twitter.downloader.TwitterDownloader(profilestore, twconn, logger)
  twdown.run(dirpath=raw_dir)
  #Analyse
  twanal = twitter.analyser.TwitterAnalyser(profilestore, logger=logger)
  twanal.run(indirpath=raw_dir, outdirpath=profile_dir)

if fbconn:
  logger.info("Running Facebook Negative Search.")
  #Search
  fbsearch = facebook.search.FacebookSearch(fbconn, profilestore, logger)
  fbsearch.search_all(namesfile)
  #Download
  fbdown = facebook.downloader.FacebookDownloader(profilestore, fbconn, logger)
  fbdown.run(dirpath=raw_dir)
  #Analyse
  fbanal = facebook.analyser.FacebookAnalyser(profilestore, logger=logger)
  fbanal.run(indirpath=raw_dir, outdirpath=profile_dir)

if liconn:
  logger.info("Running LinkedIn Negative Search.")
#  #Search
  lisearch = linkedin.search.LinkedInSearch(profilestore, logger)
  lisearch.search_all(namesfile)
#  #Download
  lidown = linkedin.downloader.LinkedInDownloader(profilestore, liconn, logger)
  lidown.run(dirpath=raw_dir)
#  #Analyse
  lianal = linkedin.analyser.LinkedInAnalyser(profilestore, logger=logger)
  lianal.run(indirpath=raw_dir, outdirpath=profile_dir)





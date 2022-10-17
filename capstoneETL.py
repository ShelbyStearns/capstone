import pyspark
from pyspark.sql import SparkSession
from pyspark.sql import SQLContext
from pyspark.sql.functions import *
from pyspark.sql.functions import udf, col, desc, asc
import pyspark.sql.functions as F
from pyspark.sql.functions import year, month, dayofmonth, \
    hour, weekofyear, date_format
from pyspark.sql.functions import isnan, col, when, count
from pyspark.context import SparkContext
from pyspark.sql.types import *
from pyspark.sql.types import StructType as R, \
            StructField as Fld, \
            DoubleType as Dbl,  \
            LongType as Long,   \
            StringType as Str,  \
            IntegerType as Int, \
            DecimalType as Dec, \
            DateType as Date,   \
            FloatType as Float, \
            TimestampType as Stamp
from pyspark.sql.window import Window as W

import datetime
import numpy as np
import configparser 
import os
import time
import boto3
import glob

config = configparser.ConfigParser()
config.read('capstone.cfg')

os.environ["AWS_ACCESS_KEY_ID"] = config["AWS"]["AWS_ACCESS_KEY_ID"]
os.environ['AWS_SECRET_ACCESS_KEY'] = config["AWS"]["AWS_SECRET_ACCESS_KEY"]
REGION = config["AWS"]["REGION"]
SOURCE_BUCKET = config["S3"]["SOURCE_BUCKET"]



def createBoto3Session(profile_name='default'): 
    """
    create boto3 session
    params: profile can be set 
    or defaults to 'default'
    """
#     import boto3
    session = boto3.session.Session(profile_name=profile_name)    
    print('Created session')
    return session


def createSessionClients(session, awsService, REGION):  
    """
    create boto3 client 
    from a session.
    
    params: aws service and region  
    """
#     import boto3
    client = session.client(awsService,
                          region_name= REGION)
    print("Created Client: " + awsService)
    return client


def createSessionResources(session, awsService, REGION): 
    """
    creates boto3 resource
    from a session
    
    params: aws service and region
    """
#     import boto3
    resource = session.resource(awsService, region_name= REGION)
    print("Created Resource: " + awsService)    
    return resource


def create_new_S3(s3_client, BUCKET, REGION):
    """
    create a new S3 bucket
    
    params: bucket name and region
    """
    print("Creating new S3 Bucket")
    try: 
        s3_new = s3_client.create_bucket(
                    ACL= 'public-read-write',
                    Bucket= BUCKET,
                    CreateBucketConfiguration={
                        'LocationConstraint': REGION})
         
        return s3_new
            
    except Exception as e:
        print(e)
        
        
def upload_multiple_files_toS3Folder(s3_client, PATH, KEY, BUCKET, folder):  
    """
    using the boto3 s3 client
    loops through a directory for file types
    uploads to an S3 bucket by partition
    """
#     import os
#     import glob    
    
    print("Uploading source files")    
    files = glob.glob(PATH + KEY)  

    try: 
        for f in files: 
            upload = s3_client.upload_file(
                Filename = f,
                Bucket = BUCKET,
                Key = folder + f.split("/")[-1])

        return upload
    
    except Exception as e:
        print(e) 


def create_spark_session():
    """
    Create a spark session
    """
    spark = SparkSession \
    .builder \
    .config("spark.jars.repositories", "https://repos.spark-packages.org/") \
    .config("spark.jars.packages", "saurfang:spark-sas7bdat:2.0.0-s_2.11, org.apache.hadoop:hadoop-aws:2.7.0, org.apache.hadoop.fs.s3a.S3AFileSystem") \
    .enableHiveSupport() \
    .getOrCreate()
    
    return spark
      
        
def readStateData():
    """
    A helper function created to read json state data from a \
    newly created s3 bucket apply data transformations and\
    output the data as a Pyspark dataframe.
    """
    spark = create_spark_session()
    spark.conf.set("spark.sql.legacy.json.allowEmptyString.enabled", True)
    
    # read state data
    states_data = spark.read \
    .option("multiline","true")\
    .json('s3a://capstonesources/SOURCE/states.json')

    # drop unneeded column
    states_data = states_data.drop(col('Abbrev'))
    
    # rename and re-case remaining headers
    states_data = states_data \
    .withColumnRenamed("State", "state_name") \
    .withColumnRenamed("Code", "state_code") 
    
    # create an 'index'
    states_data = states_data \
        .withColumn("state_id", \
                    F.monotonically_increasing_id())

    win = W.orderBy("state_id")

    states_data = states_data \
        .withColumn("state_id", \
                    F.row_number().over(win)-1)
    
    print('State data has been read into a Pyspark df')
    return state_data


def readBabyNameData():
    """
    A helper function created to read baby name data in \
    50 separate text files from a newly created s3 \
    bucket apply data transformations and
    output the data as a Pyspark dataframe.
    """
    spark = create_spark_session()

    # read baby name data
    namesbystate = spark.read \
    .option("header",False) \
    .text('s3a://capstonesources/SOURCE/*.TXT')
    
    # use split to make headers from existing columns
    split_col = \
        F.split(namesbystate['value'], ',')

    namesbystate = namesbystate \
        .withColumn('birth_year', \
                    split_col.getItem(2) \
                   )

    namesbystate = namesbystate \
        .withColumn('popularity', \
                    split_col.getItem(4) \
                   )

    namesbystate = namesbystate \
     .withColumn('birth_state_code', \
                 split_col.getItem(0) \
                )

    namesbystate = namesbystate \
        .withColumn('gender', \
                    split_col.getItem(1) \
                   )

    namesbystate = namesbystate \
        .withColumn('birth_name', \
                    split_col.getItem(3) \
                   ) \

    #drop unneeded column
    namesbystate = namesbystate.drop('value')

     # trim leading and/or trailing spaces
    namesbystate = namesbystate\
        .withColumn('birth_state_code', \
                    trim(namesbystate['birth_state_code']))

    namesbystate = namesbystate\
        .withColumn('gender', \
                    trim(namesbystate['gender']))

    namesbystate = namesbystate\
        .withColumn('birth_year', \
                    trim(namesbystate['birth_year']))

    namesbystate = namesbystate\
     .withColumn('birth_name', \
                trim(namesbystate['birth_name'])) \

    namesbystate = namesbystate\
     .withColumn('popularity', \
                trim(namesbystate['popularity']))     
    
    # make birth_name lowercase
    namesbystate = namesbystate\
     .withColumn('birth_name', \
                lower(col('birth_name')))
    
    # sort in ascending order
    namesbystate = \
        namesbystate.sort( \
        namesbystate['birth_year'].asc(), \
        namesbystate['birth_name'].asc(),
        namesbystate['popularity'].asc(), \
        namesbystate['birth_state_code'].asc())
    
    # create an 'index'
    namesbystate = namesbystate \
        .withColumn("babyName_id", \
                    F.monotonically_increasing_id())

    win = W.orderBy("babyName_id")

    namesbystate = namesbystate \
        .withColumn("babyName_id", \
                    F.row_number().over(win)-1)
    
    #reorder df
    namesbystate = namesbystate\
        .select('babyName_id', \
                'birth_year', \
                'popularity', \
                'birth_state_code', \
                'gender', \
                'birth_name')


    print('Baby name data has been read into a Pyspark df')
    return namesbystate


def readStormData():
    """
    A helper function created to read baby name data in \
    50 separate text files from a newly created s3 \
    bucket apply data transformations and
    output the data as a Pyspark dataframe.
    """
    spark = create_spark_session()

    # read storm data
    fromStormsCSV = spark.read \
        .option("header", True) \
        .option("ignoreTrailingWhiteSpace",True) \
        .option("ignoreLeadingWhiteSpace", True) \
        .csv('s3a://capstonesources/SOURCE/storms_data.csv')
    
    # trim leading and/or trailing spaces
    fromStormsCSV = fromStormsCSV\
        .withColumn('storm_id', \
                    trim(col('storm_id'))) \
        .withColumn('storm_name', \
                    trim(col('storm_name')), \
                   ) \
        .withColumn('associated_records', \
                    trim(col('associated_records')) \
                   ) \
        .withColumn('storm_time', \
                    trim(col('storm_time'))) \
        .withColumn('rec_identifier', \
                    trim(col('rec_identifier'))) \
        .withColumn('storm_type', \
                    trim(col('storm_type'))) \
        .withColumn('latitude', \
                    trim(col('latitude'))) \
        .withColumn('longitude', \
                    trim(col('longitude'))) \
        .withColumn('max_sustained_wind(kt)', \
                    trim(col('max_sustained_wind(kt)')) \
                   ) \
        .withColumn('minimum_pressure(mbar)', \
                    trim(col('minimum_pressure(mbar)'))) 
    
    # change to lowercase
    fromStormsCSV = fromStormsCSV\
        .withColumn('storm_name', \
            lower(col('storm_name')))
    
    # recast to str fields to int
    fromStormsCSV = fromStormsCSV \
        .withColumn("associated_records", \
            fromStormsCSV["associated_records"] \
        .cast(IntegerType()))

    fromStormsCSV = fromStormsCSV\
        .withColumn("max_sustained_wind(kt)",\
            fromStormsCSV["max_sustained_wind(kt)"]\
        .cast(IntegerType()))
    
    # split storm_date into new column for storm_year
    fromStormsCSV.select('storm_date').show(10,False)
    split_col = F.split(fromStormsCSV['storm_date'], '-') 

    fromStormsCSV = fromStormsCSV \
        .withColumn('storm_year', \
                    trim(split_col.getItem(0)))
    
    # create basin and ATCF_cyclone_num_forYear from \
    # the storm_id using substring
    fromStormsCSV = fromStormsCSV\
        .withColumn('ATCF_cyclone_num_forYear', \
                    col('storm_id').substr(3, 2))\
        .withColumn('basin',col('storm_id').substr(1, 2))
    
    # filter for named storms
    namedStorms = fromStormsCSV \
            .filter(col('storm_name')!= 'unnamed')
    
    
    # change data type for max_sustained_wind(kt) to float
    namedStorms = namedStorms \
        .withColumn('max_sustained_wind(kt)' \
            ,(namedStorms['max_sustained_wind(kt)']).cast(Float()))
    
    print('Storm data has been read into a Pyspark df')
    return namedStorms
         
    
def process_saffir_simpson_hurricane_wind_scale_ref(spark):
    """
    NURDAT2 data contains no reference to
    category. In order to identify category, 
    the Saffir_Simpson Wind Scale must be 
    referenced. The max_sustained_wind(kt)
    can be measured against the min-max of 
    each category's range to set the 
    category, where the storm_type is 
    hurricane

    args:
    spark = spark session parameters
    """

    spark = create_spark_session()
    
    data = [{'category': 1, 
             'sustained_wind(kt)': '64-82', 
             'max_sustained_wind(kt)': 82, 
             'min_sustained_wind(kt)': 64,
             'sustained_wind(mph)': '74-95', 
             'brief_damage_description': \
             'Power outages that could last a few to several days.'},

           {'category': 2, 
            'sustained_wind(kt)': '83-95', 
            'max_sustained_wind(kt)': 95, 
            'min_sustained_wind(kt)': 83,
            'sustained_wind(mph)': '96-110', 
            'brief_damage_description': \
            'Near-total power loss is expected \
            with outages that could last from several days to weeks.'},

           {'category': 3, 
            'sustained_wind(kt)': '96-112', 
            'max_sustained_wind(kt)': 112, 
            'min_sustained_wind(kt)': 96,
            'sustained_wind(mph)': '111-129', 
            'brief_damage_description': \
            'Electricity and water will be \
            unavailable for several days to weeks after the storm passes.'},

           {'category': 4,
            'sustained_wind(kt)': '113-136', 
            'max_sustained_wind(kt)': 136, 
            'min_sustained_wind(kt)': 113,
            'sustained_wind(mph)': '130-156', 
            'brief_damage_description': \
            'Catastrophic damage will occur; most of \
            the area will be uninhabitable for weeks or months.'},

           {'category': 5,
            'sustained_wind(kt)': '137+', 
            'min_sustained_wind(kt)': 137, 
            'sustained_wind(mph)': '157+',
            'brief_damage_description': \
            'Catastrophic damage will occur; most of the \
            area will be uninhabitable for weeks or months.'}]


    schema = StructType([
        StructField('category', Int()),
        StructField('min_sustained_wind(kt)', Int()),
        StructField('max_sustained_wind(kt)', Int()),
        StructField('sustained_wind(kt)', Str()),
        StructField('brief_damage_description', Str())
    ])

    # create data frame
    saffir_simpson_scale = spark.createDataFrame(data, schema)
#     print(saffir_simpson_scale.printSchema)
    saffir_simpson_scale.na.fill(value=0).show()   
    
    return saffir_simpson_scale
        
    # write to s3 as csv
    saffir_simpson_scale.write.mode("overwrite") \
                     .csv('s3://capstonesources/OUTPUT/saffir_simpson_scale/saffir_simpson_scale.csv')     
        
            
def process_state_ref(spark):
    """
    Leverages readStateData as a helper function to read state \
    data from an existing s3 bucket and perform a number of data\
    transformations then output the data as a Pyspark dataframe.

    A data is further processed to create a reference table 
    of the snowflake schema.

    args:
    spark = spark session parameters
    """
    
    # call helper
    state_ref = readStateData()

    # write to s3 as csv
    state_ref.write.mode("overwrite") \
                     .csv('s3://capstonesources/OUTPUT/state_ref/state_ref.csv')

def process_babyName_fact(spark):
    """
    Leverages readBabyNameData as a helper function to read \
    data from an existing s3 bucket and perform a number of data\
    transformations then output the data as a Pyspark dataframe.

    A data is further processed to create a fact table 
    of the snowflake schema.

    args:
    spark = spark session parameters
    """
    
    # call helper
    babyNames_byState_fact = readBabyNameData()

    # write to s3 as csv
    babyNames_byState_fact.write.mode("overwrite") \
                     .csv('s3a://capstonesources/OUTPUT/babyNames_byState_fact/babyNames_byState_fact.parquet')
    

def process_stormsByName_dim(spark):
    """
    Leverages readStormData as a helper function to read \
    data from an existing s3 bucket and perform a number of data\
    transformations then output the data as a Pyspark dataframe.

    A data is further processed to create a dim table 
    of the snowflake schema.

    args:
    spark = spark session parameters
    """
    
    # call helper
    storms_byName_dim = readStormData()  
    
    # write to s3 as csv
    storms_byName_dim.write.mode("overwrite") \
                     .csv('s3a://capstonesources/OUTPUT/storms_byName_dim/storms_byName_dim.csv')

    
def process_stormsLocation_dim(spark):
    """
    Leverages readStormData as a helper function to read \
    data from an existing s3 bucket and perform a number of data\
    transformations then output the data as a Pyspark dataframe.

    A data is further processed to create a dim table 
    of the snowflake schema.

    args:
    spark = spark session parameters
    """
    
    # call helper
    storms_location_dim = readStormData()  
    
    # select named storm that have storm_state_codes
    storms_location_dim = namedStorms \
    .select(['storm_id', 
            'storm_name',
            'storm_year',
            'storm_type',
            'storm_state_code' 
            ]) \
    .where(namedStorms['storm_state_code'].isNotNull())
    
    # groupby the max storm_year and drop dups
    storms_location_dim = storms_location_dim \
        .groupBy(['storm_id',
                 'storm_name',
                 'storm_type',
                 'storm_state_code'
                 ]).agg(F.max("storm_year"))\
        .dropDuplicates() 
    
    # create an 'index'
    storms_location_dim = storms_location_dim \
        .withColumn("location_id", \
                    F.monotonically_increasing_id())

    win = W.orderBy("location_id")

    storms_location_dim = storms_location_dim \
        .withColumn("location_id", \
                    F.row_number().over(win)-1)
    
    # reorder
    storms_location_dim = storms_location_dim \
        .select([
            'location_id', 
            'storm_id',
            'storm_name',
            'max(storm_year)',
            'storm_type',
            'storm_state_code' \
        ])

    # write to s3 as parquet
    storms_location_dim.write.mode("overwrite") \
                     .csv('s3a://capstonesources/OUTPUT/storms_location_dim/storms_location_dim.csv')    
    

def process_stormsSeverity_dim(spark):
    """
    Leverages readStormData as a helper function to read \
    data from an existing s3 bucket and perform a number of data\
    transformations then output the data as a Pyspark dataframe.

    A data is further processed to create a dim table 
    of the snowflake schema.

    args:
    spark = spark session parameters
    """
    
    # call helper
    storms_severity_dim = readStormData() 
    
    # select named storms with catergories
    storms_severity_dim = namedStorms \
        .select(['storm_id', 
                 'storm_name',
                 'storm_year',
                 'category',
                'max_sustained_wind(kt)'         
                ]) \
        .dropDuplicates()
    
    # groupby the max max_winds and drop dups
    storms_severity_dim = storms_severity_dim \
        .groupBy(['storm_id',
                 'storm_name',
                 'storm_year',
                 'category' 
                 ]).agg(F.max("max_sustained_wind(kt)")) \
        .dropDuplicates()
    
    # create an 'index'
    storms_severity_dim = storms_severity_dim \
        .withColumn("severity_id", \
                    F.monotonically_increasing_id())

    win = W.orderBy("severity_id")

    storms_severity_dim = storms_severity_dim \
        .withColumn("severity_id", \
                    F.row_number().over(win)-1)
    
    # reorder
    storms_severity_dim = storms_severity_dim \
        .select(['severity_id', 
                 'storm_id',
                 'storm_name',
                 'storm_year',
                 'category',
                 col('max(max_sustained_wind(kt))').alias('max_sustained_wind(kt)') \
                ])

     # write to s3 as csv
    storms_severity_dim.write.mode("overwrite") \
                     .csv('s3://capstonesources/OUTPUT/storms_severity_dim/storms_severity_dim.csv')    
    

def process_stormsMetadata_fact(spark):
    """
    Leverages readStormData as a helper function to read \
    data from an existing s3 bucket and perform a number of data\
    transformations then output the data as a Pyspark dataframe.

    A data is further processed to create a dim table 
    of the snowflake schema.

    args:
    spark = spark session parameters
    """
    
    # call helper
    storms_metadata_fact = readStormData()  
    
    # groupby category
    storms_metadata_fact = storms_metadata_fact \
        .groupBy(['storm_id',
                 'storm_name',
                 'storm_year',
                 'severity_id',
                 'location_id',
                 'storm_state_code' 
                 ]).agg(F.max("category"))\
        .dropDuplicates()
    
    # create an 'index'
    storms_metadata_fact = storms_metadata_fact \
        .withColumn("storm_meta_id", \
                    F.monotonically_increasing_id())

    win = W.orderBy("storm_meta_id")

    storms_metadata_fact = storms_metadata_fact \
        .withColumn("storm_meta_id", \
                    F.row_number().over(win)-1)
    
    # reorder and alias
    storms_metadata_fact = storms_metadata_fact \
    .select(['storm_meta_id', 
             'storm_id',
             'storm_name',
             'storm_year',
             'severity_id',
             col('max(category)').alias('category'),
             'location_id',
             'storm_state_code'
            ])
    
    # write to s3 as csv
    storms_metadata_fact.write.mode("overwrite") \
                     .csv('s3://capstonesources/OUTPUT/storms_metadata_fact/storms_metadata_fact.csv')    
      

def process_stormsBabyNames_fact(spark):
    """
    Leverages readStormData as a helper function to read \
    data from an existing s3 bucket and perform a number of data\
    transformations then output the data as a Pyspark dataframe.

    A data is further processed to create a dim table 
    of the snowflake schema.

    args:
    spark = spark session parameters
    """
    
    # call helper
    storms_babyNames_fact = readStormData()  
    
    # join storms metadata fact table to baby names fact
    meta = storms_metadata_fact \
        .select(['storm_meta_id',
                'storm_id',
                'storm_name',
                'storm_year',
                'storm_state_code',
                'category',
                'storm_meta_id',
                'storm_id',
                'location_id',
                'severity_id'
                ])

    bby = babyNames_byState_fact \
          .select(['babyName_id', 
                  'birth_name',
                  'birth_year',
                  'birth_state_code',
                  'popularity',
                  'gender'
                ])


    on = [(meta.storm_name == bby.birth_name)]
    storms_babyNames_fact = bby \
                .join(broadcast(meta), on, 'inner') \
                .select(meta['storm_meta_id']
                        ,bby['babyName_id']\
                        ,meta['storm_id'] \
                        ,meta['storm_name'] \
                        ,bby['birth_name'] \
                        ,bby['gender'] \
                        ,bby['birth_year'] \
                        ,bby['popularity'] \
                        ,meta['storm_year'] \
                        ,meta['category'] \
                        ,meta['storm_state_code'] \
                        ,bby['birth_state_code'] \
                       ) \
                .dropDuplicates()
    
    # create an 'index'
    storms_babyNames_fact = storms_babyNames_fact \
        .withColumn("storm_babyName_id", \
                    F.monotonically_increasing_id())

    win = W.orderBy("storm_babyName_id")

    storms_babyNames_fact = storms_babyNames_fact \
        .withColumn("storm_babyName_id", \
                    F.row_number().over(win)-1)
    
    # reorder 
    storms_babyNames_fact = storms_babyNames_fact \
    .select(['storm_babyName_id',
            'babyName_id',
            'storm_meta_id',
            'storm_id',
            'storm_name',
            'storm_year',
            'category',
            'storm_state_code',
            'birth_year',
            'birth_name',
            'popularity',
            'birth_state_code',
            'gender'
            ]).dropDuplicates()
    
    # write to s3 as csv
    storms_babyNames_fact.write.mode("overwrite") \
                     .csv('s3://capstonesources/OUTPUT/storms_babyNames_fact/storms_babyNames_fact.csv')    
    
    
def delete_S3(s3_resource, BUCKET):
    """
    using boto3 s3 resource, empties the contents of an S3 bucket
    then deletes the bucket
    
    args:
    s3_resource = boto3 resource for s3
    bucket = s3 bucket to empty and delete
    """
    try:
        deleteS3 = input('Ready to delete your S3 Bucket? Please answer: Yes or No...').lower()
        if deleteS3.startswith('y'):
            # to use .Bucket, the boto3 resource must be used
            s3_bucket = s3_resource.Bucket(BUCKET)
            
            s3_bucket.objects.all().delete()
            print('Bucket:', BUCKET, 'has been emptied')
            
            s3_bucket.delete()
            print('Bucket:', BUCKET, 'has been deleted')
        else: 
            print("Okay. Maybe later then.")

    except Exception as e:
        print(e)
    
        
def main():
    """
    Runs full ETL pipeline
    """
    session = createBoto3Session('default')
    s3_client = createSessionClients(session,'s3', REGION)
    s3_resource = createSessionResources(session, 's3', REGION)
    create_new_S3(s3_client, SOURCE_BUCKET, REGION)
    
    upload_multiple_files_toS3Folder(s3_client, 'source_namesbystate/', '*.TXT', SOURCE_BUCKET, 'SOURCE/')
    upload_multiple_files_toS3Folder(s3_client, 'source_weather/', '*.txt', SOURCE_BUCKET, 'SOURCE/')
    upload_multiple_files_toS3Folder(s3_client, 'source_weather/', '*.csv', SOURCE_BUCKET, 'SOURCE/')
    upload_multiple_files_toS3Folder(s3_client, 'source_states/', '*.json', SOURCE_BUCKET, 'SOURCE/')
    
    spark = create_spark_session()
    region = config.get("S3", 'region')

    # reference: https://knowledge.udacity.com/questions/73278
    from py4j.protocol import Py4JJavaError
    from pyspark.sql.utils import AnalysisException
    sc = spark.sparkContext
    sc._jsc.hadoopConfiguration().set("fs.s3a.access.key", os.environ['AWS_ACCESS_KEY_ID'])
    sc._jsc.hadoopConfiguration().set("fs.s3a.secret.key", os.environ['AWS_SECRET_ACCESS_KEY'])

    
#     spark.conf.set("spark.sql.execution.arrow.enabled", "true")
#     sc.install_pypi_package("cython==0.29.30")
#     sc.install_pypi_package("pandas==0.19.2")
#     sc.install_pypi_package("PyArrow==0.8.0")
#     sc.install_pypi_package("geopy==2.2.0")

    starttime = time.time()
    
    process_state_ref(spark)
    process_babyName_fact(spark)
    process_stormsByName_dim(spark)
    process_stormsLocation_dim(spark)
    process_stormsSeverity_dim(spark)
    process_stormsMetadata_fact(spark)
    process_stormsBabyNames_fact(spark)
    
    print('sparkify etl has completed successfully \
          duration: ', time.time() - starttime)
    
    delete_S3(s3_resource, SOURCE_BUCKET)


if __name__ == "__main__":
    main()


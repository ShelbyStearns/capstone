# Data Engineering Capstone Project: Storms and Baby Names
Shelby Stearns  
partnered with: Jasmine Cawley
____________

## Project Summary
Tropical storm season, colloquially known as hurricanes, span the beginning of June to the end of November, annually. 

Due to the '...fury of strong wind, drenching rain, dangerous storm surge and sometimes tornados', hurricanes that make landfall can be extremely dangerous and destructive to persons and property. Furthermore, hurricanes are predicted to be become more numerous and destructive due to global warming.(1)

Since the 1950s, hurricanes have been given short, distinctive names to avoid confusion and streamline communications.
Initially, female names were used. By 1979, the selections grew to include male and female names in both the Atlantic and Northern Pacific basins. The alchemy of selecting a name follows a strict procedure established by the World Meteorological Organization.(2)

An unintended consequence of associating a given name with a disastrous natural event would, in theory, negatively bias that given name.
What does the data tell us about the populary of a given name following a hurricane that made landfall in the US?
That's the question our social scientists would like to try and answer with help from two budding Data Engineers. 

(1) source: https://climate.nasa.gov/news/3184/a-force-of-nature-hurricanes-in-a-changing-climate/  
(2) source: https://oceanservice.noaa.gov/facts/storm-names.html#:~:text=Storms%20are%20given%20short%2C%20distinctive,14%2C%202018.
____

## Step 1: Scope the Project and Gather Data
____

### Baby Name Data
The Social Security Administration (SSA) has been amassing data from 1910 through present from applications for Social Security Cards.  

The SSA readily provides almost all name for researchers interested in naming trends: https://www.ssa.gov/oact/babynames/limits.html .  

Our social scientists wanted to limit their research to only state-specific data.  

The SSA makes available 6M+ records of state-specific data in 50 individual text files.  

Overall, this dataset was very 'clean'. The biggest challenge was combining all 50 files into a single dataset.  

**Please review: capstonePANDAS_EXPLORATION.ipynb for full detail.**


### State reference Data
The SSA provides a state code (example:'LA', 'ME', 'MA') to represent the state-specific data.  

Our social scientists would appreciate a reference table to decode this data, as needed.  

Using a json of State Abbrevations: https://worldpopulationreview.com/states/state-abbreviations, 
a small reference table with the 50 state codes and their full name was created.

**Please review: capstonePANDAS_EXPLORATION.ipynb for full detail.** 


### Storm Data
The Atlantic Oceanographic & Meterological Laboratory of the US Department of Commerce makes available storm data - by basin: https://www.aoml.noaa.gov/hrd/hurdat/Data_Storm.html.

We selected the revised Atlantic hurricane database (HURDAT2): https://www.nhc.noaa.gov/data/hurdat/hurdat2-1851-2021-041922.txt.

The HURDAT2 is a single comma-delimited, multilined text file (~55K records) with six-hourly data points, per storm, on the storm's location (in latitude and longitude), the maximum winds and central pressure.

This was not an easy data set to intepret or transform. The AOML-NOAA provided this pdf: https://www.aoml.noaa.gov/hrd/hurdat/hurdat2-format.pdf.

**Please review: capstonePANDAS_EXPLORATION.ipynb for full detail.** 


## Strategy 
- upload raw source data to an S3 bucket
- create an EMR cluster, 
- connect using a Spark Session
- perform a series of low-to-complex data transformations using Pyspark
    - if the transformation prove too complicated <br> (one dataset is very large and the other very small) use <br> python - pandas - to handle the most complicated transformations, <br> write the output to csv and ingest, with other sources, into Spark. 
- build the tables for the data schema
- write tables as csv to the same S3 bucket, in a separate 'output' partition

Why Spark?

> Good reasons to use Spark:  
> You actually have big data. 
> You think your data might be big in the future, and need to be ready.
> You have medium data where the Spark startup time is worth it when running locally because you will then use multiple cores.  

____

## Step 2: Explore and Assess the Data
____


To fully appreciate the 'gotchas' with these datasets:
- modeled all needed transformations using pandas
- performed various data quality checks to ensure data integrity throughout each transformation
- modeled and proofed the data schema

**Please review: capstonePANDAS_EXPLORATION.ipynb for full detail.** 

____

## Step 3: Define the Data Model
____


### 3.1 Conceptual Data Model: Map out the conceptual data model and explain why you chose that model  

Snowflake schemas are good to use when simplifing complex
relationships (many:many) with many joins.  

The hurricane (storms) date required spliting dimensional tables into further dimensional tables. A snowflake schema seemed the better fit. 

![schema](md_images/schemaCapstone.png)


### 3.2 Mapping Out Data Pipelines: List the steps necessary to pipeline the data into the chosen data model

![pipeline](md_images/pipeline.png)

1. Create an EMR cluster
2. Connect to the EMR cluster
3. Run ETL
4. Terminate AWS services

____

## Step 4: Run ETL to Model the Data
____


### 4.1 Create the data model: Build the data pipelines to create the data model.  


**Please review: capstoneETL.ipynb for full detail.** 

To run the entire pipeline:
1. create an EMR cluster in us-west-2
2. spark-submit **capstoneETL.py**

Anticipated results:
- a new s3 bucket is created
- all source data files are uploaded from the workspace to the new s3 bucket
- the entire spark job completes
- all tables are written as csv to the 'output' partition in the same s3 bucket
- validation is completed
- the s3 bucket is emptied and deleted upon user input


### 4.2 Data Quality Checks: Explain the data quality checks you'll perform to ensure the pipeline ran as expected. 

ADD DETAIL HERE

### 4.3 Data dictionary: Create a data dictionary for your data model. 

![dataDictionary](md_images/capstoneDataDict.png)

____

## Step 5: Complete Project Write Up
____


### Clearly state the rationale for the choice of tools and technologies for the project.
The baby name data is 6M+ records and anticipated to increase by thousands of records each year. 

The Udacity data lakes project was an introduction to unstructed big data and Spark. We assumed our chosen datasets would provide a similar experience. We were wrong. 

In retrospect, Spark proved more trouble than it was worth. Our datasets were 'small' by Spark standards. Complicated transformations and joins on a very small dataset to a
very large - yet structured - dataset proved tempermental. 

Additionally, our datasets are updated annually. The baby data will increase by thousands of records. However, a real-time solution, for data that Pandas handled easily, is overkill,
not to mention expensive. 

Redshift would have been a better solution. It is simplier to use and presents itself as a
standard SQL database that's quick to launch. 

That said, I'm glad we elected to try Spark. I learned more about Spark by struggling through an elective capstone, than I did through a curated project using cultivated data. 

### Propose how often the data should be updated and why.
The baby name data is updated annually. The storm data is updated annually, as well.  

The capstone pipeline would need to be updated annually, baring any radical changes to the HURDAT2 dataset.

### Write a description of how you would approach the problem differently under the following scenarios:
#### 1. The data was increased by 100x
I believe the increase in storm data from 55K to 5M records, knowing the complexity of the transformations, would do well to leverage Spark. The baby <br>
name data is fairly structured despite increasing from 6M+ to 600M+. I suspect Spark would be needed for transformations but Redshift would still be helpful for querying. 

#### 2. The data populates a dashboard that must be updated on a daily basis by 7am every day.
If you don't mind spending a ton of money on data that changes very little on a daily basis, then setup the pipeline using Airflow. 

A dashboard would be lovely. Updating daily, is a terrible idea.

#### 3. The database needed to be accessed by 100+ people.
The final capstone solution outputs the data into an S3 bucket, not a database. Database access must be managed by the social scientists.

To entertain the question based on theory... <br> Redshift, had, we used it, would likely struggle with concurrent execution, if multiple simultaneous users execute queries. Hopefully, the 100+ users would not be querying simultaneously. 

Management of these users within Redshift or via IAM would requirement additional process and management of the pipeline.
For this reason, I like depositing data in S3 and allowing users to read the data into a database of their choice. 

____

# Additional Detail

My intent was to use Pandas as a discovery and exploration tool 
only (see: **capstonPANDAS_EXPLORATION.ipynb**).

Applying multiple operations to the raw Atlantic Hurricane 
Database 2 (HURDAT2 storm) dataset proved quite challenging in Pyspark. 

HURDAT2 storm data is a multiline text file with ~55K records and requires numerous 
complex transformations to be useful for basic analysis. 

By Spark standards, this is a small dataset. 

I discovered using Pyspark to transform 
the HURDAT2 storm data seems to take disproportionately longer to 
complete relative to our other datasets, because of the 
excess overhead given the size of the cluster 
(cores and executors).

I abandon trying to transform the
raw HURDAT2 storm data in Pyspark.

Instead, for the HURDAT2 storm dataset, the more challenging 
transformations were performed using Pandas and
written into a csv file (see: **capstoneSTORMS_CSV.ipynb**). 

The csv file of semi-transformed HURDAT2 storm data ('storms.csv') 
was imported into my Spark session along with my other data sources. 

A few final data transformations, on all data sources, were done using Pyspark - 
to demonstrate some aptitude with Pyspark - before building 
the schema tables and writing to S3. This proved successful but the rework was considerable. 

In retrospect, as previously mentioned, I would have utilized Redshift instead of Spark. The datasets are NOT changing rapidly.
Both datasets are updated annually. Granted, there will be hundreds of additional records but a real-time solution on relatively small datasets was overkill. 

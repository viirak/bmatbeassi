## Overview

This project is to demonstrate 2 goals

1. Large CSV Processing
2. API and Asynchronous Task Processing

### How to install

#### Redis

Redis is required because this application use [Python-RQ](https://python-rq.org/) to manage background job queues and it is backed by Redis. Please follow the instruction on the following page to have it installed on your system.

<https://redis.io/docs/getting-started/installation/install-redis-on-mac-os/>

Assuming you have Redis installed. If not following the instruction in the above link.

To start Redis in the foreground. Open a separated terminal, and run the following command

```
redis-server
```

You can also start Redis in the background
```
brew services start redis
```
You can check the status of the running Redis
```
brew services info redis
```
To stop Redis service

```
brew services stop redis
```


#### Application

This required you have Python3.9 on your system. If not, please following the instruction HERE to get it installed.

Assuming that Python3.9, and Git are installed on your system. First clone the project repo into your local folder.

```
git clone git@github.com:viirak/bmatbeassi.git
```

Go into the project folder

```
cd bmatbeassi
```

Inside this folder, create the virtual environment so the project can run and install the required packages without affecting the system environment.

```
python3.9 -m venv venv
```

Switch to the environment, we have just created to install the required packages.

```
source venv/bin/activate
```
Install the required packages

```
pip install -r requirements.txt
```
Packages install will take a while depend on your environment. But assuming that you have everything installed without any issue. Next, we can run the application.

But first, run the database migration

```
python manage.py migrate
```

Run the application

```
python manage.py runserver
```

You should see something like this

```
System check identified no issues (0 silenced).
December 05, 2022 - 00:27:03
Django version 4.1.3, using settings 'playcount.settings'
Starting development server at http://127.0.0.1:8000/
Quit the server with CONTROL-C.
```

This mean, the application is running on your system, and it is accessible at the following URL: http://127.0.0.1:8000/

But wait, before you access the endpoint, you also need to background service workers running so that it can handle the backgound job queues.

To start the workers

```
rq worker high default low
```
To see the job queues

```
rq info
```

## How to use

From the above step, you should have
- Application running at URL http://127.0.0.1:8000/
- Redis-server running on Port: 6379 (stand alone mode)
- RQ service workers running

There are 2 endpoints that got exposed from the application.

```
1. /jobs/count/
2. /jobs/<job_id>/result/
```

These endpoints are not protected by any Auth mechanism for this project purpose, to make it easy to access.

### /jobs/count/

This endpoint (/jobs/count/) is for [count] sending the CSV file to have it processed in the background service, and get back the id of job that handle the processing.

#### Request

- Method: POST
- Headers: Content-Type: multipart/form-data
- Body params: Multipart form data with "file" field

#### Response

Response will be JSON with jobId and message.
```
{
 "jobId": "55c633d5-9caf-4a09-95db-48bfe163271a",
 "message": "file is being proccessed..."
}
```

### /jobs/<job_id>/result/

This endpoint is for retrieving the result of job that is sent with the above endpoint. The result will be a new CSV file if the job is finished, otherwise the status of the job.

#### Request

- Method: GET
- Headers: Content-Type: multipart/form-data
- URL params: job_id is the id from the "/jobs/count/" endpoint above.

#### Response

The response will be one of these
- Text: status of the job if job has not been finshed.
- File: output CSV file from the processing job

### Example

Sending request uploading ~/huge_song_play.csv file in user's home directory.

```
curl -X POST -F 'file=@~/huge_song_play.csv' http://127.0.0.1:8000/jobs/count/
```

Response JSON

```
{
    "jobId": "d42e6599-0e89-4648-a1d6-9e8ce9cbc779",
    "message": "file is being proccessed..."
}
```

Getting the result

```
curl -X GET http://127.0.0.1:8000/jobs/d42e6599-0e89-4648-a1d6-9e8ce9cbc779/result/
```

You will get the CSV file printed in the terminal.

```
Song,Date,Total Number of Plays for Date
Umbrella,2020-01-01,750
Umbrella,2020-01-02,1250
In The End,2020-01-01,7500
In The End,2020-01-02,2500
```

You can also paste this url: <http://127.0.0.1:8000/jobs/d42e6599-0e89-4648-a1d6-9e8ce9cbc779/result/> in your browser. You'll be prompted to download the file if the job is finished.

## How it work

### LargeCSVProcessing

By uploading huge file to this endpoint /jobs/count/, the file will be uploaded as chunk, and once the upload is done, it will be combined and saved as a source csv file in the tmp folder.

The uploaded csv file will be loaded into the Dask DataFrame. [Dask](dask.org) is used to handle this huge file because it has the capability of distribute the work loads into different CPU core so works can be performed in parallel. In Dask, works are organized as in Task Graph and got executed by the [Dask]scheduler on a single or distributed system cluster.

A Dask DataFrame is a collection of smaller Pandas DataFrame. These pandas DataFrames may live on disk for larger-than-memory computing on a single machine, or on many different machines in a cluster.

The CSV is processed by the CSVService class which contains two functions for doing the processing.

1. process(csv_path)
2. write(dataframe)

(1) Process function

The "process" function load the uploaded CSV into a Dask DataFrame, then pass it to the private __write function to process and write the output into a new CSV file. The uploaded csv file will be deleted when the process is finished. The output CSV file will be moved from tmp folder into Django media folder for easy serving.

```
def process(self, source_csv_path):
    df = dd.read_csv(source_csv_path)
    out_file_path, _ = self.__write(df)
    os.remove(source_csv_path)  # clean up source
    return self.__get_result_file_path(out_file_path)
```

(2) Write function

The [private] write function handles the logic of querying songs and dates, sum the total number of play, and write the output to a new CSV file. First it get the unique songs from the DataFrame, then go through each song to find its [unique] play dates. Unique play dates of a song got sorted. Loop through each date to get the data for a "song" on a "date", then sum the total number of play, and write it to the output file.

```
def __write(self, df):
    """
    Process the CSV data that are stored on Dask DataFrame.
    Write the calculated rows to a new CSV file in tmp dir
    CSV must have columns: Song, Date, Number of Plays
    """
    row_count = 0
    out_file, out_file_path, writer = self.__get_outfile_writer()
    writer.writerow(["Song", "Date", "Total Number of Plays for Date"])
    song_series = df['Song'].unique()  # npartitions *O(n*log(n))
    for song in song_series:
        df1 = df.query(f'Song == "{song}"')  # O()
        date_series = df1['Date'].unique()
        dates = list(date_series)  # temp solution
        dates.sort(key=lambda date: datetime.strptime(date, '%Y-%m-%d'))
        for d in dates:
            df2 = df.query(f'Date == "{d}" and Song == "{song}"')
            total_play = df2['Number of Plays'].sum().compute()
            writer.writerow([song, d, total_play])
            row_count += 1
    out_file.close()
    return out_file_path, row_count
```

The __write function take the loaded Dask DataFrame, then
    - Prepare the output csv file, and the [Python] csv writer module
    - Get all unique songs from the DataFrame['Song'].unique()
    - Go through each unique songs
        - Get a new DataFrame for a song (df.query(f'Song == "{song}"'))
        - Get all unique dates the song DataFrame['Date'].unique()
        - Sort the unique dates in accending order
        - Go through each date
            - Get data for a 'song' in a 'date' from the DataFrame
            - Get sum of the "Number of Plays" column
            - Write the output of [song, date, sum of played] into the output csv
    - finally close the output file, and return the output file path

Space and Time complexity is BigO: O(n*log(n))


### API and Asynchronous Task Processing

The application exposes 2 endpoints which allow the user to upload the CSV file for processing, and get the result of the processed job.

1. /jobs/count/
2. /jobs/<job_id>/result/

The first endpoint allows the user to upload the CSV file and get the response with job_id immediately without waiting for the file to be processed. Once the file is uploaded, a new job queue is created and job_id will be sent in the response immediately. The file will be processed separetely by the background service workers.

```
job_id = BackgroundService().create_new(CSVService().process, args=(tmp_uploaded_path,))
```

The system uses Python-RQ which is a simple Python library for queueing jobs and processing them asynchronously in the background with workers. It is backed by Redis server which a fast in-memory key-value datastore.

Once the file has been processed, the result will be store on Redis for a period of time set in the job queue when it is defined.

The second endpoint, /jobs/<job_id>/result/, allow the user to check for job status or getting the result -- file. It takes the job_id, and look for the job in the queue.

```
self.q.fetch_job(job_id)
```

If the job is found and its status is finished, then the result (job.result) -- file path, will be opened and sent in the response as an attachment -- force download.

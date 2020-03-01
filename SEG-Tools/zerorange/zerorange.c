#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <errno.h>
#include <string.h>
#include <pthread.h>

#define GB (1024*1024*1024)

void usage()
{
	fprintf(stderr, "USAGE:\n");
	fprintf(stderr, "zerorange [filename]\n");
}


char* filename = NULL;

int r_read(int fd, char* buffer, ssize_t size)
{
	int reserve_bytes = size;
	int read_bytes = 0;
	while(reserve_bytes > 0)
	{
		read_bytes = read(fd, buffer, reserve_bytes);
		if(read_bytes >= 0)
		{
			reserve_bytes -= read_bytes;
			buffer += read_bytes;
		} 
		else if(read_bytes <0 && errno != EINTR)
		{
			fprintf(stderr, "error happened when read");
			return -1;
		}
	}

	if (reserve_bytes == 0)
		return size;
	else
		return -1;
}


void * work_thread(void* param)
{
	unsigned long idx = (unsigned long)(param);
	struct stat statbuf ;
	char errmsg[1024];

	int ret = stat(filename, &statbuf);
	if(ret !=0)
	{
		strerror_r(errno, errmsg, 1024);
		fprintf(stderr, "Thread-%2d:failed to stat %s (%s)\n",idx, filename, errmsg);
		return (void*)NULL;
	}
	memset(errmsg, '\0', 1024);
	off_t begin = idx * GB;
	off_t end = statbuf.st_size > (idx * GB + GB)? (idx+1)*GB : statbuf.st_size ;

	int fd = open(filename , O_RDONLY);
	if(fd < 0)
	{
		strerror_r(errno, errmsg, 1024);
		fprintf(stderr, "Thread-%2d:failed to open %s (%s)\n",idx, filename, errmsg);
		return (void*)NULL;
	}

	off_t pos  = lseek(fd, begin, SEEK_SET);
	if(pos < 0)
	{
		strerror_r(errno, errmsg, 1024);
		fprintf(stderr, "failed to lseek to  %llu (%s) \n",begin, errmsg);
	}

	char *buffer = malloc(4096);
	char *base = malloc(4096) ; 
	memset(base, '\0', 4096);


	ssize_t read_bytes = 0 ;
	ssize_t current_size = 0 ;
	off_t offset = begin;
	off_t offset_start = -1;
	ssize_t length  = 0;

	while(offset < end)
	{
		if (offset + 4096 <=end)
		{
			current_size = 4096;
		}
		else 
		{
			current_size = end - offset ;
		}
		read_bytes = r_read(fd, buffer,current_size);
		if(read_bytes < 0)
		{
			strerror_r(errno, errmsg, 1024);
			fprintf(stderr,"failed to read , offset %llu (%s)", offset, errmsg);
			break; 
		}

		ret = memcmp(buffer, base, current_size);
		if(ret == 0)
		{
			if (offset_start == -1)
			{
				offset_start = offset ; 
			}
			length += current_size;
		}
		else
		{
			if(offset_start != -1)
			{
				fprintf(stderr ,"%20llu~%10llu\n",offset_start, length);
				offset_start = -1;
				length = 0;
			}
		}

		offset += read_bytes;

	}
	if(offset_start != -1)
	{
		fprintf(stderr, "%20llu~%10llu\n",offset_start, length);
	}

	return (void*) NULL;

}
int main(int argc, char* argv[])
{
	int ret ;
	char errmsg[1024] ; 
	struct stat statbuf; 

	if (argc != 2)
	{
		fprintf(stderr, "invalid parameter number , at least 2 parameter");
		usage();
		return 0 ;
	}

	filename = (char*) malloc(1024) ; 
	memset(filename, '\0', 1024);
	memset(errmsg, '\0', 1024); 

	strncpy(filename, argv[1],1023);	
	ret = stat(filename, &statbuf);
	if(ret)
	{
		strerror_r(errno, errmsg, sizeof(errmsg));
		fprintf(stderr, "failed to stat %s\n (%s)\n", filename, errmsg);
	}

	unsigned long long fsize = statbuf.st_size ;
	int num_worker = (fsize + GB -1) / GB ;
	int i ;
	unsigned long idx ; 
	pthread_t *tid_array = (pthread_t*) malloc(num_worker * sizeof(pthread_t));

	for(i = 0; i < num_worker; i++)
	{
		idx = i ;
		ret = pthread_create(&(tid_array[i]), NULL, work_thread, (void*) idx);
		if(ret)
		{
			fprintf(stderr,"failed to create thread %d\n", i);
		}
	}

	for(i = 0 ; i < num_worker ; i++)
	{
		pthread_join(tid_array[i], NULL);
	}

	return ret ;
}

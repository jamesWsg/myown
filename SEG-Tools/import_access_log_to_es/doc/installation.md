# 日志导入程序安装 

## 前提条件

* 安装前启动好Elasticsearch
* 安装好Python依赖库

## 打开RADOS Gateway的OP log

修改所有node `/etc/ceph/ceph.conf`
```
rgw enable ops log = true

```
重启RADOS Gateway

```
/etc/init.d/radosgw restart
```
随便操作bucket,object
然后通过如下命令查看配置是否生效
```
radosgw-admin log list
```

## 创建Elasticsearch mappings
只需要在一个node运行即可

先查询一下是否已经创建索引三个索引
```
#curl -XGET 'localhost:9200/raw_access_log/_mapping/_doc?pretty'
#curl -XGET 'localhost:9200/access_log/_mapping/_doc?pretty'
#curl -XGET 'localhost:9200/object/_mapping/_doc?pretty'

```
正在情况下，应该返回404，即没有创建过。


创建raw_access_log索引并定义mapping,命令如下：

```
curl -XPUT 'localhost:9200/raw_access_log?pretty' -H 'Content-Type: application/json' -d'
{
    "mappings": {
        "_doc": {
            "properties": {
                "bucket": {
                    "type": "keyword"
                },
                "time": {
                    "type": "date",
                    "format": "YYYY-MM-DD HH:mm:ss"
                },
                "time_local": {
                    "type": "date",
                    "format": "YYYY-MM-DD HH:mm:ss"
                },
                "remote_addr": {
                    "type": "ip"
                },
                "user": {
                    "type": "keyword"
                },
                "operation": {
                    "type": "keyword"
                },
                "uri": {
                    "type": "keyword"
                },
                "http_status": {
                    "type": "keyword"
                },
                "error_code": {
                    "type": "keyword"
                },
                "bytes_sent": {
                    "type": "long"
                },
                "bytes_received": {
                    "type": "long"
                },
                "object_size": {
                    "type": "long"
                },
                "total_time": {
                    "type": "integer"
                },
                "user_agent": {
                    "type": "keyword"
                },
                "referrer": {
                    "type": "keyword"
                }
            }
        }
    }
}
'


```

创建access_log索引并定义mapping,命令如下：

```
curl -XPUT 'localhost:9200/access_log?pretty' -H 'Content-Type: application/json' -d'
{
    "mappings": {
        "_doc": {
            "properties": {
                "bucket": {
                    "type": "keyword"
                },
                "time": {
                    "type": "date",
                    "format": "YYYY-MM-DD HH:mm:ss"
                },
                "time_local": {
                    "type": "date",
                    "format": "YYYY-MM-DD HH:mm:ss"
                },
                "remote_addr": {
                    "type": "ip"
                },
                "user": {
                    "type": "keyword"
                },
                "operation": {
                    "type": "keyword"
                },
                "uri": {
                    "type": "keyword"
                },
                "http_status": {
                    "type": "keyword"
                },
                "error_code": {
                    "type": "keyword"
                },
                "bytes_sent": {
                    "type": "long"
                },
                "bytes_received": {
                    "type": "long"
                },
                "object_size": {
                    "type": "long"
                },
                "total_time": {
                    "type": "integer"
                },
                "user_agent": {
                    "type": "keyword"
                },
                "referrer": {
                    "type": "keyword"
                },
                "handle_flag": {
                    "type": "keyword"
                }
            }
        }
    }
}
'

```

创建object索引并定义mapping,命令如下：

```

curl -XPUT 'localhost:9200/object?pretty' -H 'Content-Type: application/json' -d'
{
	"mappings": {
		"_doc": {
		"dynamic_templates": [
                { "zh_cn": {
                      "match":              "user_meta.*",
                      "mapping": {
                          "type":           "text",
						  "date_detection": false,
                          "analyzer":       "ik_max_word",
						  "search_analyzer": "ik_max_word"
                      }
                }}
            ],
			"properties": {
				"bucket": {
					"type": "keyword"
				},
				"name": {
					"type": "text",
					"analyzer": "ik_max_word",
					"search_analyzer": "ik_max_word"
				},
				"owner": {
					"properties": {
						"id": {
							"type": "keyword"
						},
						"display_name": {
							"type": "text",
							"analyzer": "ik_max_word",
							"search_analyzer": "ik_max_word"
						}
					}
				},
				"meta": {
					"properties": {
						"size": {
							"type": "long"
						},
						"mtime": {
							"type": "date",
							"format":"YYYY-MM-DD HH:mm:ss"
						},
						"etag": {
							"type": "keyword"
						}
					}
				},
				"user_meta": {
					"type": "object",
					"dynamic": true,
					"properties": {}
				}
			}
		}
	}
}
'

```

## 上传程序


```
# ls
import_log_2_es.1.4.tar
#

```

## 安装

所有node都需要安装

先解压缩

```
#tar xvf import_log_2_es.1.1.tar.gz
#cd import_log_2_es.1.1
#

```

修改配置文件 `import_radosgw_access_log_to_es.conf`


执行安装 

```
#sh install.sh

```
## 验证安装

过3分钟后查看日志
```
/var/log/import_radosgw_access_log.log

```

## 卸载(如果需要)


```
#sh uninstall.sh
#

```


## 查询示例


```
curl -XGET 'localhost:9200/_search?pretty' -H 'Content-Type: application/json' -d'
{
  "query": { 
    "bool": { 
      "must": [
        {  "multi_match" : {
      "query" : "要查询的关键字",
      "fields" : [ "name", "user_meta.*" ] 
    }
		
		}
      ],
      "filter": [ 
        { "term":  { "bucket": "exmample-bucket-name" }},
		{ "range": { "meta.size": { "gte": 1,"lte" : 4213784307 }}}
      ]
    }
  },
  "from": 0,
  "size": 10
}
'

```
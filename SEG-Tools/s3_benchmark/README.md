## 使用说明

配置完成后，在项目主目录下运行`python s3_benchmark.py`

## 配置说明

| 字段                 | 意义                             |
| ------------------ | ------------------------------ |
| host               | 被测试的节点的ip                      |
| prepare            | 测试前是否需要准备数据                    |
| download_rate      | 测试中download的比例                 |
| upload_rate        | 测试中upload的比例                   |
| retry              | 测试中若向s3发送的请求发生错误，重试的次数         |
| min_file_size      | 上传/下载对象大小的最小值（Byte）            |
| max_file_size      | 上传/下载对象大小的最大值（Byte）            |
| concurrency        | 并发数                            |
| multipart_thresh   | 触发分片上传/下载的文件大小（Byte）           |
| account_quantity   | 测试用的账户数量                       |
| account_prefix     | 账户名称前缀                         |
| bucket_per_account | 每个账户下桶的数量                      |
| bucket_prefix      | 桶名称的前缀                         |
| object_per_bucket  | 每个桶下对象的数量                      |
| object_prefix      | 对象名称前缀                         |
| test_duration      | 测试时长（s）                        |
| operation_interval | 每次上传/下载之间的间隔（s）                |
| overwrite_old_file | 若为True，则写入新文件会覆盖旧文件；否则，始终生成新文件 |


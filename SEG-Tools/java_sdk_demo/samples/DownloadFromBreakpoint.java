import com.amazonaws.ClientConfiguration;
import com.amazonaws.auth.AWSCredentials;
import com.amazonaws.auth.AWSStaticCredentialsProvider;
import com.amazonaws.auth.BasicAWSCredentials;
import com.amazonaws.client.builder.AwsClientBuilder;
import com.amazonaws.services.s3.AmazonS3;
import com.amazonaws.services.s3.AmazonS3ClientBuilder;
import com.amazonaws.services.s3.model.GetObjectRequest;
import com.amazonaws.services.s3.model.S3Object;
import com.amazonaws.util.IOUtils;

import java.io.*;
import java.util.Properties;

public class DownloadFromBreakpoint {

    private  static  void writeDownloadProcess(long total_file_size,long chunk_size,long downloaded_size){
        File configFile = new File("download.properties");

        try {
            Properties props = new Properties();
            props.setProperty("total_file_size", Long.toString(total_file_size));
            props.setProperty("chunk_size", Long.toString(chunk_size));
            props.setProperty("downloaded_size", Long.toString(downloaded_size));
            FileWriter writer = new FileWriter(configFile);
            props.store(writer, "download process");
            writer.close();
        }catch (Exception ex) {
            System.out.println("Write download.properties Error!");
        }
    }

    /*
     * 断点下载操作演示。可以运行到一半强行关闭程序，然后再次运行
     * 本地文件"download.properties"用于记录下载进度，正常下载后会删除
     */
    public static void main(String[] args) {

        String existingBucketName  = "andy-bucket";
        String keyName             = "ubuntu-16.04-server-amd64.iso";
        String localFilePath            = "E:\\code\\s3_multipart_upload\\local_file.iso";

        String endPoint = "http://172.17.59.72/";
        String accessKey = "JF06KCDJIAMO8Q3OJQAS";
        String secretKey = "gHnrKj1Vlb6s9IQZRrMDywhTLeNBL2UUMCGeetsf";
        long partSize = 5242880 * 2; // 设置分片大小，要大于5M

        AWSCredentials credentials = new BasicAWSCredentials(accessKey, secretKey);

        ClientConfiguration clientConfiguration = new ClientConfiguration();
        clientConfiguration.setSignerOverride("S3SignerType");

        AmazonS3 s3Client = AmazonS3ClientBuilder.standard()
                .withCredentials(new AWSStaticCredentialsProvider(credentials))
                .withClientConfiguration(clientConfiguration)
                .withEndpointConfiguration(new AwsClientBuilder.EndpointConfiguration(endPoint,"us-east-1"))
                .build();


        File configFile = new File("download.properties");

        //下面3个参数不一定全要，主要是用于校验
        long stored_total_file_size = 0;//记录总文件大小
        long stored_chunk_size = 0;//记录分片大小
        long stored_downloaded_size = 0;//记录已经下载的大小

        long remaining ;
        long downloaded_size ;

        try {
            FileReader reader = new FileReader(configFile);
            Properties props = new Properties();
            props.load(reader);

            stored_total_file_size = Long.parseLong(props.getProperty("total_file_size","0"));
            stored_chunk_size = Long.parseLong(props.getProperty("chunk_size","0"));
            stored_downloaded_size = Long.parseLong(props.getProperty("downloaded_size","0"));

            reader.close();
        } catch (FileNotFoundException ex) {
            System.out.println("没有文件，说明没有下载到一半的情况");
        } catch (Exception ex) {
            System.out.println("Error !");
        }

        S3Object object = s3Client.getObject(
                new GetObjectRequest(existingBucketName, keyName));

        long total_file_size = object.getObjectMetadata().getContentLength();

        long partNum = 0;
        boolean seekFirst = false;

        //从本地文件中取得下载记录，并且做适当的校验
        if ((stored_total_file_size == total_file_size) && (stored_chunk_size == partSize)){
            //看看之前已经下载了多少块了
            remaining = stored_total_file_size - stored_downloaded_size;
            partNum = stored_downloaded_size / stored_chunk_size;
            seekFirst = true;
        }else {
            //好像有点异常，需要整个文件全部重新下载
            remaining = total_file_size;
            try{
                File file = new File(localFilePath);
                if(file.exists() && !file.delete()){
                    System.out.println("Delete download.properties is failed.");
                }
            }catch(Exception e){
                e.printStackTrace();
            }

        }

        long offset ;
        long length ;
        //一直运行，直到下载完成
        while (remaining > 0){

            offset = partNum * partSize;
            length = Math.min(remaining, partSize);
            GetObjectRequest rangeObjectRequest = new GetObjectRequest(
                    existingBucketName, keyName);
            System.out.println("offset:" + offset + "  length:"+ length);
            rangeObjectRequest.setRange(offset, offset + length - 1);
            S3Object objectPortion = s3Client.getObject(rangeObjectRequest);
            try {
            RandomAccessFile localFile = new RandomAccessFile(localFilePath, "rw");

            if (seekFirst){
                //上次下载最后的一个分片很有可能不完整，所以不能从最后添加,要覆盖最后的分片
                localFile.seek(offset);
                seekFirst = false;
            }else{
                File f = new File(localFilePath);
                long fileLength = f.length();
                //在尾部添加
                localFile.seek(fileLength);
            }

            //在本地文件中添加下载好的部分内容
            localFile.write(IOUtils.toByteArray(objectPortion.getObjectContent()));
            localFile.close();

            } catch (Exception ex) {
                ex.printStackTrace();
            }

            remaining = remaining - length;
            downloaded_size = offset + length;
            partNum = partNum + 1;

            //记录下载进程
            writeDownloadProcess(total_file_size,partSize,downloaded_size);
            System.out.println("写入第" + partNum + "分片   总大小:"+ total_file_size + "  已经下载大小:"+ downloaded_size);

            if (total_file_size == downloaded_size){
                try{
                    File file = new File("download.properties");
                    if(!file.delete()){
                        System.out.println("Delete download.properties is failed.");
                    }
                }catch(Exception e){
                    e.printStackTrace();
                }
            }

        }


    }
}

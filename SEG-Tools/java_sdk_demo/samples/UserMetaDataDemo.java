import com.amazonaws.ClientConfiguration;
import com.amazonaws.auth.AWSCredentials;
import com.amazonaws.auth.AWSStaticCredentialsProvider;
import com.amazonaws.auth.BasicAWSCredentials;
import com.amazonaws.client.builder.AwsClientBuilder;
import com.amazonaws.services.s3.AmazonS3;
import com.amazonaws.services.s3.AmazonS3ClientBuilder;
import com.amazonaws.services.s3.model.*;

import java.io.*;
import java.net.URLDecoder;
import java.net.URLEncoder;

public class UserMetaDataDemo {
    /*
     * 本程序演示如何上传自定义的meta data，如何取得meta data
     */
    public static void main(String[] args)  {
        String existingBucketName = "andy-bucket";
        String keyName = "1.txt";

        String endPoint = "http://172.17.59.72/";
        String accessKey = "TUUMEEX7GCRDT25C03NX";
        String secretKey = "HaOe0ADXcFYdi7MAzS1pULAqwzABdOSaz15oiUcP";

        AWSCredentials credentials = new BasicAWSCredentials(accessKey, secretKey);

        ClientConfiguration clientConfiguration = new ClientConfiguration();
        clientConfiguration.setSignerOverride("S3SignerType");

        AmazonS3 s3Client = AmazonS3ClientBuilder.standard()
                .withCredentials(new AWSStaticCredentialsProvider(credentials))
                .withClientConfiguration(clientConfiguration)
                .withEndpointConfiguration(new AwsClientBuilder.EndpointConfiguration(endPoint, "us-east-1"))
                .build();

        setMeta(s3Client,existingBucketName,keyName);
        getMetaWithoutObject(s3Client,existingBucketName,keyName);
        getMetaWithObject(s3Client,existingBucketName,keyName);


    }

    //上传时添加自己定义的meta data
    private static void setMeta(AmazonS3 s3Client,String existingBucketName,String keyName) {
         try{
             ObjectMetadata metadata = new ObjectMetadata();
             // 注意：key不要用中文，value不要使用过长的字 2K以下
             // 因为Metadata是放在HTTP头中的，key可以使用"-"做分隔，不要使用"_".
             // value里边的中文上传时要编码
             metadata.addUserMetadata("my-key","1");//你可以自己上传md5,sha1等，留着将来校验
             metadata.addUserMetadata("my-key2", URLEncoder.encode("abc","UTF-8"));
             metadata.addUserMetadata("my-key3", URLEncoder.encode("a中文字符串1","UTF-8"));
             //metadata.setContentEncoding("gzip");
             //metadata.setContentType("video/mp4"); //需要在浏览器播放视频时可能需要设置

             s3Client.putObject(new PutObjectRequest(existingBucketName, keyName, createSampleFile()).withMetadata(metadata));

             //metadata上传后不可以修改。一个变通的办法是copy这个object带上新的metadata.

         } catch (Exception e) {
             System.out.print(e.getMessage());
         }
    }

    //下载object时获取自己定义的meta data
    private static void getMetaWithObject(AmazonS3 s3Client,String existingBucketName,String keyName) {

        S3Object object = s3Client.getObject(new GetObjectRequest(existingBucketName, keyName));
        ObjectMetadata objectMetadata = object.getObjectMetadata();

        printMetadata(objectMetadata);
    }

    //不下载文件获取自己定义的meta data
    private static void getMetaWithoutObject(AmazonS3 s3Client,String existingBucketName,String keyName) {

        ObjectMetadata objectMetadata = s3Client.getObjectMetadata(new GetObjectMetadataRequest(existingBucketName, keyName));
        printMetadata(objectMetadata);

    }

    private static void printMetadata(ObjectMetadata objectMetadata){
        System.out.println("常用的Metadata: " );
        System.out.println("Content-Type: "  + objectMetadata.getContentType());

        //一般而言ETag去了字符串中的引号就是md5,java已经帮忙去了引号
        System.out.println("ETag: "  + objectMetadata.getETag());
        System.out.println("ContentMD5: "  + objectMetadata.getContentMD5());//其实为空
        System.out.println("VersionId: "  + objectMetadata.getVersionId());
        System.out.println("ContentEncoding: "  + objectMetadata.getContentEncoding());
        System.out.println("LastModified: "  + objectMetadata.getLastModified());
        System.out.println("ContentLength: "  + objectMetadata.getContentLength());

        System.out.println("UserMetadata: "  + objectMetadata.getUserMetadata());

        try{
            // value里边的中文下载后要解码
            System.out.println("UserMetadata:my-key3: "  + URLDecoder.decode(objectMetadata.getUserMetadata().get("my-key3"),"UTF-8"));
        } catch (Exception e) {
            System.out.print(e.getMessage());
        }
        System.out.println("---------------------------------------------------------" );
    }

    private static File createSampleFile() throws IOException {
        File file = File.createTempFile("aws-java-sdk-", ".txt");
        file.deleteOnExit();

        Writer writer = new OutputStreamWriter(new FileOutputStream(file));
        writer.write("abcdefghijklmnopqrstuvwxyz\n");
        writer.close();

        return file;
    }
}

import java.net.URL;

import com.amazonaws.ClientConfiguration;
import com.amazonaws.HttpMethod;
import com.amazonaws.auth.AWSCredentials;
import com.amazonaws.auth.AWSStaticCredentialsProvider;
import com.amazonaws.auth.BasicAWSCredentials;
import com.amazonaws.client.builder.AwsClientBuilder;
import com.amazonaws.services.s3.AmazonS3;
import com.amazonaws.services.s3.AmazonS3ClientBuilder;
import com.amazonaws.services.s3.model.GeneratePresignedUrlRequest;

public class GeneratePreSignedUrl {

    /*
     * 本程序演示如何生成预签名对象 URL
     * 常见的场景：非公开的的对象（匿名用户无法访问），临时生成一个URL供用户访问，这个URL只在一定的时间内有效
     * 如果有一批可以公开的对象(如普通图片)，可以设置bucket的policy让匿名用户访问这个bucket里边的全部或者部分内容
     */
    public static void main(String[] args) {
        String existingBucketName  = "andy-bucket";
        String keyName             = "有趣的电影.mp4";

        String endPoint = "http://172.17.59.72";
        String accessKey = "YQQVVCKIHDG2EQP79X6D";
        String secretKey = "wK0BOaavE6lBHQXYTa3xDUaf6wQrKMAl5oynzS4f";

        AWSCredentials credentials = new BasicAWSCredentials(accessKey, secretKey);

        ClientConfiguration clientConfiguration = new ClientConfiguration();
        clientConfiguration.setSignerOverride("S3SignerType");

        AmazonS3 s3client = AmazonS3ClientBuilder.standard()
                .withCredentials(new AWSStaticCredentialsProvider(credentials))
                .withClientConfiguration(clientConfiguration)
                .withEndpointConfiguration(new AwsClientBuilder.EndpointConfiguration(endPoint,"us-east-1"))
                .build();

        try {
            System.out.println("生成预签名的URL...");
            java.util.Date expiration = new java.util.Date();
            long milliSeconds = expiration.getTime();
            milliSeconds += 1000 * 60 * 60; // 1小时内此URL有效
            expiration.setTime(milliSeconds);

            GeneratePresignedUrlRequest generatePresignedUrlRequest =
                    new GeneratePresignedUrlRequest(existingBucketName, keyName);
            generatePresignedUrlRequest.setMethod(HttpMethod.GET);//设置客户端对这个URL操作的HTTP的method
            generatePresignedUrlRequest.setExpiration(expiration);//设置URL超时时间

            URL url = s3client.generatePresignedUrl(generatePresignedUrlRequest);

            System.out.println("预签名的URL = " + url.toString());

        }  catch (Exception e) {
            System.out.println(e.getMessage());
        }
    }
}
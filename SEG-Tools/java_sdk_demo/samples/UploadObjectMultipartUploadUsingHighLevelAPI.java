import java.io.File;

import com.amazonaws.ClientConfiguration;
import com.amazonaws.auth.AWSCredentials;
import com.amazonaws.auth.AWSStaticCredentialsProvider;
import com.amazonaws.auth.BasicAWSCredentials;
import com.amazonaws.client.builder.AwsClientBuilder;
import com.amazonaws.services.s3.AmazonS3;
import com.amazonaws.services.s3.AmazonS3ClientBuilder;
import com.amazonaws.services.s3.transfer.*;

import com.amazonaws.AmazonServiceException;
import com.amazonaws.services.s3.transfer.TransferManager;
import com.amazonaws.services.s3.transfer.TransferManagerBuilder;

public class UploadObjectMultipartUploadUsingHighLevelAPI {

    public static void main(String[] args) throws Exception {
        String existingBucketName  = "andy-bucket";
        String keyName             = "ubuntu-16.04-server-amd64_java.iso";
        String file_path            = "E:\\code\\s3_multipart_upload\\ubuntu-16.04-server-amd64.iso";

        String endPoint = "http://172.17.59.72/";
        String accessKey = "TUUMEEX7GCRDT25C03NX";
        String secretKey = "HaOe0ADXcFYdi7MAzS1pULAqwzABdOSaz15oiUcP";

        AWSCredentials credentials = new BasicAWSCredentials(accessKey, secretKey);

        ClientConfiguration clientConfiguration = new ClientConfiguration();
        clientConfiguration.setSignerOverride("S3SignerType");

        AmazonS3 s3Client = AmazonS3ClientBuilder.standard()
                .withClientConfiguration(clientConfiguration)
                .withCredentials(new AWSStaticCredentialsProvider(credentials))
                .withEndpointConfiguration(new AwsClientBuilder.EndpointConfiguration(endPoint, "us-west-2"))
                .build();

        File f = new File(file_path);

        /*
         * 其实就是对分片上传的基础API做了封装
         */

        TransferManager xfer_mgr = TransferManagerBuilder.standard()
                .withS3Client(s3Client)
                .build();

        try {
            Upload xfer = xfer_mgr.upload(existingBucketName, keyName, f);
            xfer.waitForCompletion();   //等待上传完成
        } catch (AmazonServiceException e) {
            System.err.println(e.getErrorMessage());
            System.exit(1);
        }
        xfer_mgr.shutdownNow();

    }
}
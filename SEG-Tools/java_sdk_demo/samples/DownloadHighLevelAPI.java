import com.amazonaws.AmazonServiceException;
import com.amazonaws.ClientConfiguration;
import com.amazonaws.auth.AWSCredentials;
import com.amazonaws.auth.AWSStaticCredentialsProvider;
import com.amazonaws.auth.BasicAWSCredentials;
import com.amazonaws.client.builder.AwsClientBuilder;
import com.amazonaws.services.s3.AmazonS3;
import com.amazonaws.services.s3.AmazonS3ClientBuilder;
import com.amazonaws.services.s3.transfer.*;

import java.io.File;

public class DownloadHighLevelAPI {

    public static void main(String[] args) throws Exception {
        String existingBucketName  = "andy-bucket";
        String keyName             = "ubuntu-16.04-server-amd64_java.iso";
        String file_path            = "E:\\code\\s3_multipart_upload\\ubuntu-16.04-server-amd64.iso";

        String endPoint = "http://172.17.59.72/";
        String accessKey = "MDHLYYKFMKGR3VK4UBHJ";
        String secretKey = "479wsPL8ELae8FBeyPptG7dF2o8x5giTHpa3w6eM";

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
        //单个文件
        //Download download = xfer_mgr.download(existingBucketName,"filename",new File("filename"));
        //下载整个目录
        MultipleFileDownload download = xfer_mgr.downloadDirectory(existingBucketName,"testdir",new File("./testdir"));
        try {
            download.waitForCompletion();
        } catch (AmazonServiceException e) {
            System.err.println(e.getErrorMessage());
            System.exit(1);
        }
        xfer_mgr.shutdownNow();

    }
}

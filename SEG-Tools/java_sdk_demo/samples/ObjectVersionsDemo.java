import com.amazonaws.AmazonClientException;
import com.amazonaws.AmazonServiceException;
import com.amazonaws.ClientConfiguration;
import com.amazonaws.auth.AWSCredentials;
import com.amazonaws.auth.AWSStaticCredentialsProvider;
import com.amazonaws.auth.BasicAWSCredentials;
import com.amazonaws.client.builder.AwsClientBuilder;
import com.amazonaws.services.s3.AmazonS3;
import com.amazonaws.services.s3.AmazonS3ClientBuilder;
import com.amazonaws.services.s3.model.*;

import java.io.*;

public class ObjectVersionsDemo {
    /*
     * 本程序演示了对象存储中对bucket和object的基本操作
     */
    public static void main(String[] args) throws IOException {


        String endPoint = "http://172.17.59.72/";
        String accessKey = "MDHLYYKFMKGR3VK4UBHJ";
        String secretKey = "479wsPL8ELae8FBeyPptG7dF2o8x5giTHpa3w6eM";

        AWSCredentials credentials = new BasicAWSCredentials(accessKey, secretKey);

        ClientConfiguration clientConfiguration = new ClientConfiguration();
        clientConfiguration.setSignerOverride("S3SignerType");

        BucketVersioningConfiguration versioning_config = new BucketVersioningConfiguration();
        versioning_config.setStatus(BucketVersioningConfiguration.ENABLED);

        AmazonS3 s3 = AmazonS3ClientBuilder.standard()
                .withCredentials(new AWSStaticCredentialsProvider(credentials))
                .withClientConfiguration(clientConfiguration)
                .withEndpointConfiguration(new AwsClientBuilder.EndpointConfiguration(endPoint,"us-east-1"))
                .build();

        String bucket_name = "andy-bucket";

        try {
            GetBucketVersioningConfigurationRequest query_request = new GetBucketVersioningConfigurationRequest(bucket_name);
            System.out.println(s3.getBucketVersioningConfiguration(query_request).getStatus());
            SetBucketVersioningConfigurationRequest request = new SetBucketVersioningConfigurationRequest(bucket_name,versioning_config);
            s3.setBucketVersioningConfiguration(request);
            System.out.println(s3.getBucketVersioningConfiguration(query_request).getStatus());
            BucketPolicy policy = s3.getBucketPolicy(bucket_name);
            System.out.println(policy.getPolicyText());
            s3.shutdown();

        } catch (AmazonServiceException ase) {
            // 服务器端返回错误而的抛出的异常，也就是说客户端口已经连上了服务器，但由于某种原因被拒绝
            System.out.println("服务器端异常:    " + ase.getMessage());
        } catch (AmazonClientException ace) {
            // 客户端抛出的异常，比如连不上服务器
            System.out.println("客户端异常: " + ace.getMessage());
        }
    }



}

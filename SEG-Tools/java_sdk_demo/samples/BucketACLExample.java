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

public class BucketACLExample {
    /*
     * 本程序演示 Bucket ACL权限的修改
     */
    public static void main(String[] args){
        String bucketName  = "andy-bucket";

        String endPoint = "http://172.17.59.72";
        String accessKey = "MDHLYYKFMKGR3VK4UBHJ";
        String secretKey = "479wsPL8ELae8FBeyPptG7dF2o8x5giTHpa3w6eM";

        AWSCredentials credentials = new BasicAWSCredentials(accessKey, secretKey);

        ClientConfiguration clientConfiguration = new ClientConfiguration();
        clientConfiguration.setSignerOverride("S3SignerType");

        AmazonS3 s3Client = AmazonS3ClientBuilder.standard()
                .withCredentials(new AWSStaticCredentialsProvider(credentials))
                .withClientConfiguration(clientConfiguration)
                .withEndpointConfiguration(new AwsClientBuilder.EndpointConfiguration(endPoint,"us-east-1"))
                .build();

        try {

            //AccessControlList acl;

            /*
             * 权限分为Read，Write,ReadAcp,WriteAcp,FullControl
             * FullControl指前面四个的总和，并不是Read，Write总和
             *
             */
            System.out.println(s3Client.getBucketLocation(bucketName));
            System.out.println(s3Client.getBucketAcl(bucketName));
            s3Client.setBucketAcl(bucketName,CannedAccessControlList.PublicReadWrite);

            System.out.println(s3Client.getBucketAcl(bucketName));


        }  catch (AmazonServiceException ase) {
            // 服务器端返回错误而的抛出的异常，也就是说客户端口已经连上了服务器，但由于某种原因被拒绝
            System.out.println("服务器端异常:    " + ase.getMessage());
        } catch (AmazonClientException ace) {
            // 客户端抛出的异常，比如连不上服务器
            System.out.println("客户端异常: " + ace.getMessage());
        }
    }
}

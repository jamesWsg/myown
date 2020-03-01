import com.amazonaws.AmazonClientException;
import com.amazonaws.AmazonServiceException;
import com.amazonaws.ClientConfiguration;
import com.amazonaws.auth.AWSCredentials;
import com.amazonaws.auth.AWSStaticCredentialsProvider;
import com.amazonaws.auth.BasicAWSCredentials;
import com.amazonaws.client.builder.AwsClientBuilder;
import com.amazonaws.services.s3.AmazonS3;
import com.amazonaws.services.s3.AmazonS3ClientBuilder;
import com.amazonaws.services.s3.model.AccessControlList;
import com.amazonaws.services.s3.model.CanonicalGrantee;
import com.amazonaws.services.s3.model.GroupGrantee;
import com.amazonaws.services.s3.model.Permission;


public class ACLExample {
    /*
     * 本程序演示ACL权限的修改
     */
    public static void main(String[] args){
        String bucketName  = "andy-bucket";
        String keyName     = "[迅雷下载www.kuhema.com]猿族崛起BD1280高清英语中字.rmvb";

        String endPoint = "http://172.17.59.72";
        String accessKey = "JF06KCDJIAMO8Q3OJQAS";
        String secretKey = "gHnrKj1Vlb6s9IQZRrMDywhTLeNBL2UUMCGeetsf";

        AWSCredentials credentials = new BasicAWSCredentials(accessKey, secretKey);

        ClientConfiguration clientConfiguration = new ClientConfiguration();
        clientConfiguration.setSignerOverride("S3SignerType");

        AmazonS3 s3Client = AmazonS3ClientBuilder.standard()
                .withCredentials(new AWSStaticCredentialsProvider(credentials))
                .withClientConfiguration(clientConfiguration)
                .withEndpointConfiguration(new AwsClientBuilder.EndpointConfiguration(endPoint,"us-east-1"))
                .build();

        try {

            AccessControlList acl = new AccessControlList();

            /*
             * 权限分为Read，Write,ReadAcp,WriteAcp,FullControl
             * FullControl指前面四个的总和，并不是Read，Write总和
             *
             */
            //给某个用户加权限
            acl.grantPermission(new CanonicalGrantee("sds_test"), Permission.ReadAcp);
            acl.grantPermission(GroupGrantee.AuthenticatedUsers, Permission.Read);

            //给某个email地址加权限
            // acl.grantPermission(new EmailAddressGrantee("user@email.com"), Permission.WriteAcp);

            //设置owner
            /*
            Owner owner = new Owner();
            owner.setId("852b113e7a2f25102679df27bb0ae12b3f85be6f290b936c4393484beExample");
            owner.setDisplayName("display-name");
            acl.setOwner(owner);
            */

            acl.setOwner(s3Client.getObjectAcl(bucketName,keyName).getOwner());

            s3Client.setObjectAcl(bucketName, keyName, acl);

        }  catch (AmazonServiceException ase) {
            // 服务器端返回错误而的抛出的异常，也就是说客户端口已经连上了服务器，但由于某种原因被拒绝
            System.out.println("服务器端异常:    " + ase.getMessage());
        } catch (AmazonClientException ace) {
            // 客户端抛出的异常，比如连不上服务器
            System.out.println("客户端异常: " + ace.getMessage());
        }
    }
}
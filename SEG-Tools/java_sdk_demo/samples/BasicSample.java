import java.io.BufferedReader;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.io.Writer;
import java.util.UUID;

import com.amazonaws.AmazonClientException;
import com.amazonaws.AmazonServiceException;
import com.amazonaws.auth.AWSCredentials;
import com.amazonaws.auth.BasicAWSCredentials;
import com.amazonaws.auth.AWSStaticCredentialsProvider;
import com.amazonaws.services.s3.AmazonS3;
import com.amazonaws.services.s3.AmazonS3ClientBuilder;
import com.amazonaws.client.builder.AwsClientBuilder;
import com.amazonaws.services.s3.model.Bucket;
import com.amazonaws.services.s3.model.GetObjectRequest;
import com.amazonaws.services.s3.model.ListObjectsRequest;
import com.amazonaws.services.s3.model.ObjectListing;
import com.amazonaws.services.s3.model.PutObjectRequest;
import com.amazonaws.services.s3.model.S3Object;
import com.amazonaws.services.s3.model.S3ObjectSummary;

import com.amazonaws.ClientConfiguration;

public class BasicSample {
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

        AmazonS3 s3 = AmazonS3ClientBuilder.standard()
                .withCredentials(new AWSStaticCredentialsProvider(credentials))
                .withClientConfiguration(clientConfiguration)
                .withEndpointConfiguration(new AwsClientBuilder.EndpointConfiguration(endPoint,"us-east-1"))
                .build();

        String bucketName = "my-first-s3-bucket-" + UUID.randomUUID();
        String key = "MyObjectKey";

        try {
            /*
             * 创建bucket,bucket的名字要符合URI中hostname
             */
            System.out.println("正在创建 bucket: " + bucketName + "\n");
            s3.createBucket(bucketName);

            /*
             * 查看bucket列表
             */
            System.out.println("bucket列表:");
            for (Bucket bucket : s3.listBuckets()) {

                System.out.println(" - " + bucket.getName());
            }
            System.out.println();

            /*
             * 上传到一个object到bucket
             */
            System.out.println("上传文件到S3存储\n");
            s3.putObject(new PutObjectRequest(bucketName, key, createSampleFile()));

            /*
             * 下载object
             */
            System.out.println("下载object");
            S3Object object = s3.getObject(new GetObjectRequest(bucketName, key));
            System.out.println("Content-Type: "  + object.getObjectMetadata().getContentType());
            displayTextInputStream(object.getObjectContent());

            /*
             * 遍历bucket中object - 可以指定前缀，但不可以直接搜索
             * 注意一下结果可能被截取了，需要使用 AmazonS3.listNextBatchOfObjects(...)操作再取后面的object
             */
            System.out.println("object 列表");
            ObjectListing objectListing = s3.listObjects(new ListObjectsRequest()
                    .withBucketName(bucketName)
                    .withPrefix("My"));
            for (S3ObjectSummary objectSummary : objectListing.getObjectSummaries()) {
                System.out.println(" - " + objectSummary.getKey() + "  " +
                                   "(size = " + objectSummary.getSize() + ")");
            }
            System.out.println();

            /*
             * 删除object
             */
            System.out.println("删除object\n");
            s3.deleteObject(bucketName, key);

            /*
             * 删除bucket - 只有空的bucket才可以删除
             */
            System.out.println("删除bucket： " + bucketName + "\n");
            s3.deleteBucket(bucketName);


            s3.shutdown();

        } catch (AmazonServiceException ase) {
            // 服务器端返回错误而的抛出的异常，也就是说客户端口已经连上了服务器，但由于某种原因被拒绝
            System.out.println("服务器端异常:    " + ase.getMessage());
        } catch (AmazonClientException ace) {
            // 客户端抛出的异常，比如连不上服务器
            System.out.println("客户端异常: " + ace.getMessage());
        }
    }

    /**
     * 创建时间文件用来演示
     */
    private static File createSampleFile() throws IOException {
        File file = File.createTempFile("aws-java-sdk-", ".txt");
        file.deleteOnExit();

        Writer writer = new OutputStreamWriter(new FileOutputStream(file));
        writer.write("abcdefghijklmnopqrstuvwxyz1234567890\n");
        writer.close();

        return file;
    }

    /**
     * 显示InputStream中的数据
     */
    private static void displayTextInputStream(InputStream input) throws IOException {
        BufferedReader reader = new BufferedReader(new InputStreamReader(input));
        while (true) {
            String line = reader.readLine();
            if (line == null) break;

            System.out.println("    " + line);
        }
        System.out.println();
    }

}

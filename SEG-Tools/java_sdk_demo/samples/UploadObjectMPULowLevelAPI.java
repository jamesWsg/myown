import java.io.File;
import java.util.ArrayList;
import java.util.List;

import com.amazonaws.ClientConfiguration;
import com.amazonaws.auth.AWSCredentials;
import com.amazonaws.auth.AWSStaticCredentialsProvider;
import com.amazonaws.auth.BasicAWSCredentials;
import com.amazonaws.client.builder.AwsClientBuilder;
import com.amazonaws.services.s3.AmazonS3;
import com.amazonaws.services.s3.AmazonS3ClientBuilder;
import com.amazonaws.services.s3.model.AbortMultipartUploadRequest;
import com.amazonaws.services.s3.model.CompleteMultipartUploadRequest;
import com.amazonaws.services.s3.model.InitiateMultipartUploadRequest;
import com.amazonaws.services.s3.model.InitiateMultipartUploadResult;
import com.amazonaws.services.s3.model.PartETag;
import com.amazonaws.services.s3.model.UploadPartRequest;

public class UploadObjectMPULowLevelAPI {
    /*
     * 本程序演示分片上传大文件的流程
     */
    public static void main(String[] args) {
        String existingBucketName  = "andy_bucket";
        String keyName             = "ubuntu-16.04-server-amd64_2.iso";
        String filePath            = "E:\\code\\s3_multipart_upload\\ubuntu-16.04-server-amd64.iso";

        String endPoint = "http://172.17.59.72/";
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


        // partETags用于保存已经上传对象的列表
        List<PartETag> partETags = new ArrayList<PartETag>();

        // 第1步: 初始化，申请一个UploadId，后续流程通过这个UploadId关联
        InitiateMultipartUploadRequest initRequest = new
                InitiateMultipartUploadRequest(existingBucketName, keyName);

        InitiateMultipartUploadResult initResponse =
                s3Client.initiateMultipartUpload(initRequest);

        System.out.println("新申请到的UploadId:" + initResponse.getUploadId());

        File file = new File(filePath);
        long contentLength = file.length();
        long partSize = 5242880 * 2; // 设置分片大小，需要大于5M

        try {
            // 第2步: 分片上传，可以多线程同时.
            long filePosition = 0;
            for (int i = 1; filePosition < contentLength; i++) {
                // 只有最后一个分片可以小于5M
                partSize = Math.min(partSize, (contentLength - filePosition));

                System.out.print("正在上传第" + i + "个分片...");
                // 创建生成分片上传的请求
                UploadPartRequest uploadRequest = new UploadPartRequest()
                        .withBucketName(existingBucketName).withKey(keyName)
                        .withUploadId(initResponse.getUploadId()).withPartNumber(i)
                        .withFileOffset(filePosition)
                        .withFile(file)
                        .withPartSize(partSize);

                // 上传分片，并且保存结果到List供最后使用
                partETags.add(
                        s3Client.uploadPart(uploadRequest).getPartETag());
                System.out.println("第" + i + "个分片上传完成了");

                filePosition += partSize;
            }

            // 第3步: 告诉服务器上传全部完成，让服务器完成组装动作
            CompleteMultipartUploadRequest compRequest = new
                    CompleteMultipartUploadRequest(
                    existingBucketName,
                    keyName,
                    initResponse.getUploadId(),
                    partETags);
            System.out.println("正在请求服务器组装动作...");
            s3Client.completeMultipartUpload(compRequest);
            System.out.println("服务器完成组装完成");
        } catch (Exception e) {
            //如果上传失败，或者组装失败，调用abort让服务器清理之前的已经上传的分片
            //如果不调用abort可能会造成服务器存储里边分片数据一起保留着。
            //也可以不清除，保留分片数据下次继续上传。
            s3Client.abortMultipartUpload(new AbortMultipartUploadRequest(
                    existingBucketName, keyName, initResponse.getUploadId()));
        }
    }
}
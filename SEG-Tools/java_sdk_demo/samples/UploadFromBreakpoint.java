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
import com.amazonaws.services.s3.model.*;

public class UploadFromBreakpoint {

    private static MultipartUpload getMultipartUpload(AmazonS3 s3Client,String existingBucketName,String keyName){

        ListMultipartUploadsRequest allMultpartUploadsRequest =
                new ListMultipartUploadsRequest(existingBucketName);
        MultipartUploadListing multipartUploadListing =
                s3Client.listMultipartUploads(allMultpartUploadsRequest);

        for (MultipartUpload multipartUpload:multipartUploadListing.getMultipartUploads()) {
            System.out.println(multipartUpload.getKey() + ':' +multipartUpload.getUploadId());
            if(multipartUpload.getKey().equals(keyName)){
                //查到与keyName相同的分片
                return  multipartUpload;
            }

        }
        return null;
    }

    private static void uploadFromBreakpoint(AmazonS3 s3Client,String existingBucketName, String filePath,
                                             String keyName,MultipartUpload multipartUpload){

        List<PartSummary>  partSummaryList =
                s3Client.listParts(new ListPartsRequest(existingBucketName,multipartUpload.getKey() ,
                        multipartUpload.getUploadId())).getParts();
        List<PartETag> partETags = new ArrayList<PartETag>();

        for (PartSummary partSummary:partSummaryList) {
            System.out.println(partSummary.getPartNumber() + ':' +partSummary.getETag() + ':' + partSummary.getSize());
            partETags.add(new PartETag(partSummary.getPartNumber(),partSummary.getETag()) );
        }
        int uploaded_parts_num = partSummaryList.size();

        File file = new File(filePath);
        long contentLength = file.length();
        long partSize = 5242880 * 2; // 设置分片大小,要和之前的一样

        try {
            long filePosition = 0;
            for (int i = 1; filePosition < contentLength; i++) {
                // Last part can be less than 5 MB. Adjust part size.
                partSize = Math.min(partSize, (contentLength - filePosition));

                if(i <= uploaded_parts_num){
                    //最好校验已经上传分片的大小,ETAG等
                    System.out.println("跳过第" + i + "个分片 ...");
                }else{
                    System.out.print("正在上传第" + i + "个分片...");
                    // 上传未上传过的分片
                    UploadPartRequest uploadRequest = new UploadPartRequest()
                            .withBucketName(existingBucketName).withKey(keyName)
                            .withUploadId(multipartUpload.getUploadId()).withPartNumber(i)
                            .withFileOffset(filePosition)
                            .withFile(file)
                            .withPartSize(partSize);

                    partETags.add( s3Client.uploadPart(uploadRequest).getPartETag());
                    System.out.println("第" + i + "个分片上传完成");
                }

                filePosition += partSize;
            }

            // 最后完成组装
            CompleteMultipartUploadRequest compRequest = new
                CompleteMultipartUploadRequest(
                        existingBucketName,
                        keyName,
                        multipartUpload.getUploadId(),
                        partETags);
            System.out.println("告诉服务器上传全部完成，让服务器完成组装动作");
            s3Client.completeMultipartUpload(compRequest);
        } catch (Exception e) {
            //上传的有问题，取消,下次全部重传
            s3Client.abortMultipartUpload(new AbortMultipartUploadRequest(existingBucketName,
                    keyName, multipartUpload.getUploadId()));
        }

    }

    /*
     * 从头开始上传就是普通的分片上传，具体解释可以查看分片上传
     */
    private static void uploadFromBeginning(AmazonS3 s3Client,String existingBucketName,
                                            String filePath, String keyName){


        List<PartETag> partETags = new ArrayList<PartETag>();

        // Step 1: Initialize.
        InitiateMultipartUploadRequest initRequest = new
                InitiateMultipartUploadRequest(existingBucketName, keyName);

        InitiateMultipartUploadResult initResponse =
                s3Client.initiateMultipartUpload(initRequest);

        System.out.println("新申请到的UploadId:" + initResponse.getUploadId());


            File file = new File(filePath);
            long contentLength = file.length();
            long partSize = 5242880 * 2; // 设置分片大小

            try {
                // Step 2: Upload parts.
                long filePosition = 0;
                for (int i = 1; filePosition < contentLength; i++) {
                    // Last part can be less than 5 MB. Adjust part size.
                    partSize = Math.min(partSize, (contentLength - filePosition));

                    System.out.print("正在上传第" + i + "个分片...");
                    // Create request to upload a part.
                    UploadPartRequest uploadRequest = new UploadPartRequest()
                            .withBucketName(existingBucketName).withKey(keyName)
                            .withUploadId(initResponse.getUploadId()).withPartNumber(i)
                            .withFileOffset(filePosition)
                            .withFile(file)
                            .withPartSize(partSize);

                    // Upload part and add response to our list.
                    partETags.add(
                            s3Client.uploadPart(uploadRequest).getPartETag());
                    System.out.println("第" + i + "个分片上传完成");
                    filePosition += partSize;
                }

                // Step 3: Complete.
                CompleteMultipartUploadRequest compRequest = new
                        CompleteMultipartUploadRequest(
                        existingBucketName,
                        keyName,
                        initResponse.getUploadId(),
                        partETags);
                System.out.println("告诉服务器上传全部完成，让服务器完成组装动作");
                s3Client.completeMultipartUpload(compRequest);
            } catch (Exception e) {
                System.out.println("上传出错了,下次也许可以重传");
                //如果这里abort,下次就不能续传了，所以不要取消
                //s3Client.abortMultipartUpload(new AbortMultipartUploadRequest(existingBucketName,
                // keyName, initResponse.getUploadId()));
            }

        }

    private static void  uploadLargeFile(AmazonS3 s3Client,String existingBucketName, String filePath, String keyName){
        MultipartUpload multipartUpload = getMultipartUpload(s3Client,existingBucketName,keyName);
        if(multipartUpload == null){
            //在服务器没有查询到分片，从头开始上传
            uploadFromBeginning(s3Client,existingBucketName,filePath,keyName);
        }else {
            //在服务器查询到分片，从断点处上传
            uploadFromBreakpoint(s3Client,existingBucketName,filePath,keyName,multipartUpload);
        }
    }

    /*
     * 断点上传操作演示。该功能基于分片上传API实现
     * 可以运行到一半强行关闭程序，然后再次运行
     * 上传的分片在存储的服务器端查询
     */
    public static void main(String[] args)  {
        String existingBucketName  = "andy_bucket";
        String keyName             = "ubuntu-16.04-server-amd64_5.iso";
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

        uploadLargeFile(s3Client,existingBucketName, filePath, keyName);

    }
}
import java.io.IOException;

import org.apache.http.HttpHost;
import org.apache.http.auth.AuthScope;
import org.apache.http.auth.UsernamePasswordCredentials;
import org.apache.http.client.CredentialsProvider;
import org.apache.http.impl.client.BasicCredentialsProvider;
import org.apache.http.impl.nio.client.HttpAsyncClientBuilder;
import org.elasticsearch.action.search.SearchRequest;
import org.elasticsearch.action.search.SearchResponse;
import org.elasticsearch.client.RestClient;
import org.elasticsearch.client.RestClientBuilder;
import org.elasticsearch.client.RestHighLevelClient;
import org.elasticsearch.index.query.MultiMatchQueryBuilder;
import org.elasticsearch.index.query.QueryBuilders;
import org.elasticsearch.search.SearchHit;
import org.elasticsearch.search.SearchHits;
import org.elasticsearch.search.builder.SearchSourceBuilder;
import static org.elasticsearch.index.query.QueryBuilders.termQuery;


public class SearchDemo {
    /*
     * Meta data 搜索演示
     *
     */
    public static void main(String[] args) throws IOException {
        String q = "中国";//要查询的关键字
        String bucket_name = "andy-bucket"; //查询所在的bucket

        /*
         * 提供用户名和密码
         */
        final CredentialsProvider credentialsProvider = new BasicCredentialsProvider();
        credentialsProvider.setCredentials(AuthScope.ANY,
                new UsernamePasswordCredentials("read_only_user", "read_only_user"));

        /*
         * 提供机器，可以是一台或者多台
         */
        RestClientBuilder builder = RestClient.builder(
                new HttpHost("172.17.59.72", 9200, "http"),
                new HttpHost("172.17.59.73", 9200, "http")
        )
                .setHttpClientConfigCallback(new RestClientBuilder.HttpClientConfigCallback() {
                    public HttpAsyncClientBuilder customizeHttpClient(HttpAsyncClientBuilder httpClientBuilder) {
                        return httpClientBuilder.setDefaultCredentialsProvider(credentialsProvider);
                    }
                });

        RestHighLevelClient client = new RestHighLevelClient(builder);

        SearchRequest searchRequest = new SearchRequest("object");//查询object这个索引，这个不要修改
        SearchSourceBuilder searchSourceBuilder = new SearchSourceBuilder();
        searchSourceBuilder.query(QueryBuilders.boolQuery()
                .must(new MultiMatchQueryBuilder(q,"name", "user_meta.*")) //查询所在字段
                .filter(termQuery("bucket", bucket_name)) )   //所有在所有bucket里边查，这一行可以去了
                .size(3)  //这两个参数用于分页
                .from(0); // 从0开始计数

        searchRequest.source(searchSourceBuilder);


        SearchResponse response = client.search(searchRequest);
        SearchHits hits = response.getHits();
        if (hits.totalHits > 0) {
            System.out.println("一共搜到" + hits.totalHits+ "条结果:");
            System.out.println("本页" + hits.getHits().length+ "条结果:");
            for (SearchHit hit : hits) {
                //score越高，搜索的结果越准确,getSourceAsString里边包含所有详细内容
                System.out.println("score:"+hit.getScore()+":\t"+hit.getSourceAsString());

                //下面两项可以用来取对象
                System.out.println("bucket:\t"+hit.getSourceAsMap().get("bucket").toString());
                System.out.println("name:\t"+hit.getSourceAsMap().get("name").toString());
            }
        } else {
            System.out.println("搜到0条结果");
        }

        client.close();

    }

}

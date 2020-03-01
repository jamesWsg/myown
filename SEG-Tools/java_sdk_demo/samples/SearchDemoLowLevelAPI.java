//import org.apache.http.Header;
import org.apache.http.HttpEntity;
import org.apache.http.HttpHost;
//import org.apache.http.RequestLine;
import org.apache.http.auth.AuthScope;
import org.apache.http.auth.UsernamePasswordCredentials;
import org.apache.http.client.CredentialsProvider;
import org.apache.http.entity.ContentType;
import org.apache.http.impl.client.BasicCredentialsProvider;
import org.apache.http.impl.nio.client.HttpAsyncClientBuilder;
import org.apache.http.nio.entity.NStringEntity;
import org.apache.http.util.EntityUtils;
import org.elasticsearch.client.Response;
import org.elasticsearch.client.RestClient;
import org.elasticsearch.client.RestClientBuilder;

import org.json.*;
import java.io.IOException;
import java.util.Collections;
import java.util.Map;

public class SearchDemoLowLevelAPI {
    public static void main(String[] args) throws IOException {
        String q = "中国";//要查询的关键字
        String bucket_name = "andy-bucket"; //查询所在的bucket

        Integer from = 0;
        Integer size = 10;

        final CredentialsProvider credentialsProvider = new BasicCredentialsProvider();
        credentialsProvider.setCredentials(AuthScope.ANY,
                new UsernamePasswordCredentials("user", "password"));


        RestClientBuilder builder = RestClient.builder(new HttpHost("www.andyzou.org", 80))
                .setHttpClientConfigCallback(new RestClientBuilder.HttpClientConfigCallback() {
                    @Override
                    public HttpAsyncClientBuilder customizeHttpClient(HttpAsyncClientBuilder httpClientBuilder) {
                        return httpClientBuilder.setDefaultCredentialsProvider(credentialsProvider);
                    }
                });


        RestClient restClient = builder.build();

        Map<String, String> params = Collections.emptyMap();
        /*
         * fields 指定要搜索的字段 name 即keyname，user_meta.* 指所有自定义的meta
         */
        String jsonString = "{" +
                "   \"query\": { " +
                "   \"bool\": { " +
                "     \"must\": [ " +
                "    {  \"multi_match\" : {" +
                "        \"query\" : \"" + q +"\"," +
                "                \"fields\" : [ \"name\", \"user_meta.*\" ]" +
                "     }" +
                "     }" +
                "   ]," +
                "      \"filter\": [" +
                "    { \"term\":  { \"bucket\": \"" + bucket_name +"\" }}" +
                "   ]" +
                "    }" +
                "   }," +
                "   \"from\": " + from +"," +
                "      \"size\": " + size +
                "}";
        HttpEntity entity = new NStringEntity(jsonString, ContentType.APPLICATION_JSON);

        Response response = restClient.performRequest("GET", "/_search.php",params, entity);
        // RequestLine requestLine = response.getRequestLine();
        // HttpHost host = response.getHost();
        // int statusCode = response.getStatusLine().getStatusCode();
        // Header[] headers = response.getHeaders();
        String responseBody = EntityUtils.toString(response.getEntity());

        JSONObject jsonResponse = new JSONObject(responseBody);

        JSONObject hits = jsonResponse.getJSONObject("hits");
        Integer totalHits = hits.getInt("total");
        System.out.println("一共搜到" + totalHits+ "条结果:");
        if(totalHits > 0) {

            JSONArray hitsResults = hits.getJSONArray("hits");
            int resultSize = hitsResults.length();
            for (int i = 0; i < resultSize; i++) {

                JSONObject jsonRsult = hitsResults.getJSONObject(i);

                JSONObject jsonDoc = jsonRsult.getJSONObject("_source");

                //score越高，搜索的结果越准确,_source里边包含所有详细内容
                System.out.println("score:" + jsonRsult.getDouble("_score") + ":\t" + jsonDoc.toString());

                //下面两项可以用来取对象
                System.out.println("bucket:\t" + jsonDoc.getString("bucket"));
                System.out.println("name:\t" + jsonDoc.getString("name"));
            }
        } else {
            System.out.println("搜到0条结果");
        }
        restClient.close();
    }
}

        /*
        * {
  "query": {
    "bool": {
      "must": [
        {  "multi_match" : {
      "query" : "",
      "fields" : [ "name", "user_meta.*" ]
    }

		}
      ],
      "filter": [
        { "term":  { "bucket": "andy_bucket" }},
		{ "range": { "meta.size": { "gte": 1,"lte" : 1213784307 }}}
      ]
    }
  },

  "from": 0,
  "size": 10
}
     */
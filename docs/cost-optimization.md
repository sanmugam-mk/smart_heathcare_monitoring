# Cost Optimization & Serverless Economics

## Design Strategy

The system is engineered as a 100% serverless application to guarantee **zero baseline cost ($0.00/month idle cost)** while providing automatic scalability.

```
+------------------+-----------------------+---------------------------------------+
| Service          | Pricing Model         | Academic / Free Tier Coverage         |
+------------------+-----------------------+---------------------------------------+
| AWS Lambda       | Per execution & ms    | 1,000,000 free requests / month       |
| Amazon DynamoDB  | PAY_PER_REQUEST       | 25 GB storage & 25 WCU / RCU free     |
| AWS IoT Core     | Per MQTT message      | 2,250,000 free messages / month       |
| API Gateway      | Per 1M HTTP requests  | 1,000,000 free requests / month       |
| Amazon SNS       | Per published message | 1,000,000 free publishes / month      |
| Amazon S3        | Per GB stored & API   | 5 GB standard storage free            |
| Amazon Cognito   | Monthly Active Users  | 50,000 MAUs free                      |
+------------------+-----------------------+---------------------------------------+
```

---

## Cost Prevention Measures Enforced

1. **Elimination of Provisioned Infrastructure**:
   - No EC2 instances.
   - No always-running Relational Databases (RDS).
   - No NAT Gateways or Application Load Balancers (ALBs) which incur fixed $30-$50/month charges.
2. **DynamoDB On-Demand Billing (`PAY_PER_REQUEST`)**:
   - Zero capacity provisioning. Charges accrue strictly when read/write operations execute.
3. **CloudWatch Log Retention Policy**:
   - Enforced a **7-day retention limit** across all AWS Lambda Log Groups (`/aws/lambda/EHR-*`) to prevent indefinite CloudWatch storage accumulation.
4. **Short TTL Presigned S3 URLs**:
   - Prevents stale S3 URLs and avoids public egress bandwidth abuse.

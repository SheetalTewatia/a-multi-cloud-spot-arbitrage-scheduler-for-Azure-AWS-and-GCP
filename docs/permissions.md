# Cloud permissions

Tide uses least-privilege credentials. This file lists exactly what each phase needs and
is updated as phases add features.

Credentials are never stored in the repo. AWS uses the standard boto3 chain (`AWS_PROFILE`,
environment variables, or `~/.aws/credentials`); Azure uses a service principal from
environment variables (see `.env.example`).

## Phases 2-3: price and eviction-risk collection

### AWS

| Action | Why |
| --- | --- |
| `ec2:DescribeSpotPriceHistory` | Current spot price per availability zone |
| `pricing:GetProducts` | On-demand list prices (Price List API) |

Both are read-only, have no charge, and create no resources. IAM policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "TidePriceCollection",
      "Effect": "Allow",
      "Action": ["ec2:DescribeSpotPriceHistory", "pricing:GetProducts"],
      "Resource": "*"
    }
  ]
}
```

(Neither action supports resource-level permissions, so `Resource` must be `*`.)

### Eviction risk

None. The AWS Spot Instance Advisor data is a public JSON file
(`spot-bid-advisor.s3.amazonaws.com/spot-advisor-data.json`), and Azure uses a static table.

### Azure

None. The [Retail Prices API](https://learn.microsoft.com/rest/api/cost-management/retail-prices/azure-retail-prices)
is public and needs no authentication.

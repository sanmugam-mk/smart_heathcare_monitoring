# Data Model Specification

## Overview

The database design utilizes Amazon DynamoDB in `PAY_PER_REQUEST` billing mode. The schema is optimized for single-digit millisecond read/write access patterns covering patient EHR demographic records, high-frequency IoT time-series telemetry streams, risk evaluations, and emergency alert logs.

---

## Entity Relationship & Schema Details

```
+-------------------+             +-----------------------+
|     Patients      |             |     VitalReadings     |
+-------------------+             +-----------------------+
| PK: PatientId (S) | 1         * | PK: PatientId (S)     |
| Name (S)          |-----------< | SK: Timestamp (S)     |
| Age (N)           |             | HeartRate (N)         |
| Gender (S)        |             | SpO2 (N)              |
| CreatedAt (S)     |             | Temperature (N)       |
| UpdatedBy (S)     |             | DeviceID (S)          |
+-------------------+             | Source (S)            |
          |                       +-----------------------+
          | 1
          |                       +-----------------------+
          |                       |    RiskAssessments    |
          |                       +-----------------------+
          | 1                   * | PK: PatientId (S)     |
          +---------------------< | SK: Timestamp (S)     |
          |                       | RiskLevel (S)         |
          |                       | RiskScore (N)         |
          |                       | DetectedAbnormalities |
          |                       | Explanation (L)       |
          |                       +-----------------------+
          | 1
          |                       +-----------------------+
          |                       |        Alerts         |
          |                       +-----------------------+
          | 1                   * | PK: PatientId (S)     |
          +---------------------< | SK: Timestamp (S)     |
          |                       | RiskLevel (S)         |
          |                       | VitalsSnapshot (M)    |
          |                       | Message (S)           |
          |                       | SNSMessageId (S)      |
          |                       | Status (S)            |
          |                       +-----------------------+
          | 1
          |                       +-----------------------+
          |                       |       Documents       |
          |                       +-----------------------+
          | 1                   * | PK: DocumentId (S)    |
          +---------------------< | GSI: PatientIdIndex   |
                                  |   (GSI PK: PatientId) |
                                  | Filename (S)          |
                                  | S3Key (S)             |
                                  | UploadedAt (S)        |
                                  +-----------------------+
```

---

## DynamoDB Table Specifications

### 1. `Patients` Table (Existing Core Table)
- **Primary Key**:
  - **Partition Key (HASH)**: `PatientId` (String, e.g. `"P001"`)
- **Billing Mode**: `PAY_PER_REQUEST`
- **Attributes**:
  - `PatientId` (S): Unique patient identifier.
  - `Name` (S): Full legal name.
  - `Age` (N): Age in years.
  - `Gender` (S): Male / Female / Other.
  - `CreatedAt` (S): ISO-8601 creation timestamp.
  - `UpdatedBy` (S): User email who last modified record.
- **Primary Access Patterns**:
  - `GetItem(PK="P001")`: Retrieve patient profile.
  - `Scan()`: Search/list all active patient profiles.
  - `PutItem(...)`: Create or update patient profile.

---

### 2. `VitalReadings` Table (New Telemetry Time-Series Table)
- **Primary Key**:
  - **Partition Key (HASH)**: `PatientId` (String, e.g. `"P001"`)
  - **Sort Key (RANGE)**: `Timestamp` (String, ISO-8601 UTC `YYYY-MM-DDTHH:mm:ss.SSSZ`)
- **Billing Mode**: `PAY_PER_REQUEST`
- **Attributes**:
  - `PatientId` (S): Patient ID associated with the reading.
  - `Timestamp` (S): Exact measurement timestamp.
  - `HeartRate` (N): Heart rate in Beats Per Minute (BPM).
  - `SpO2` (N, optional): Blood oxygen saturation percentage, only when measured.
  - `Temperature` (N, optional): Body temperature in degrees Celsius, only when measured.
  - `DeviceID` (S): Unique hardware ID or simulator ID.
  - `Source` (S): Telemetry origin (for example `"ESP32"`); unmeasured values are omitted rather than fabricated.
- **Primary Access Patterns**:
  - **Get Latest Vitals**: `Query(PK="P001", ScanIndexForward=False, Limit=1)` -> Single-digit ms lookup for latest reading.
  - **Get Vital Trend Line**: `Query(PK="P001", KeyConditionExpression="Timestamp BETWEEN :t1 AND :t2", ScanIndexForward=True)` -> Fetches chronological readings for line chart.
  - **Put Telemetry**: `PutItem(...)` -> Ingestion Lambda inserts high-frequency telemetry.

---

### 3. `RiskAssessments` Table (New Evaluation History Table)
- **Primary Key**:
  - **Partition Key (HASH)**: `PatientId` (String, e.g. `"P001"`)
  - **Sort Key (RANGE)**: `Timestamp` (String, ISO-8601 UTC)
- **Billing Mode**: `PAY_PER_REQUEST`
- **Attributes**:
  - `PatientId` (S): Patient ID.
  - `Timestamp` (S): Timestamp matching evaluated vital reading.
  - `RiskLevel` (S): Status classification (`"NORMAL"` | `"WARNING"` | `"HIGH"`).
  - `RiskScore` (N): Cumulative numerical risk score (0 to 10).
  - `DetectedAbnormalities` (L): List of strings indicating triggered threshold flags (e.g. `["ELEVATED_HEART_RATE", "LOW_SPO2"]`).
  - `Explanation` (L): List of detailed clinical justification statements.
- **Primary Access Patterns**:
  - **Get Latest Risk Assessment**: `Query(PK="P001", ScanIndexForward=False, Limit=1)` -> Renders current health risk card on Doctor Dashboard.
  - **Get Assessment History**: `Query(PK="P001", ScanIndexForward=False, Limit=10)` -> Renders historical risk timeline.

---

### 4. `Alerts` Table (New Emergency Notification Log Table)
- **Primary Key**:
  - **Partition Key (HASH)**: `PatientId` (String, e.g. `"P001"`)
  - **Sort Key (RANGE)**: `Timestamp` (String, ISO-8601 UTC)
- **Billing Mode**: `PAY_PER_REQUEST`
- **Attributes**:
  - `PatientId` (S): Patient ID.
  - `Timestamp` (S): Alert creation timestamp.
  - `RiskLevel` (S): Always `"HIGH"`.
  - `VitalsSnapshot` (M): Embedded snapshot map (`{HeartRate: 118, SpO2: 91, Temperature: 38.4}`).
  - `Message` (S): Formatted clinical emergency alert summary.
  - `SNSMessageId` (S): Amazon SNS published message ID reference.
  - `Status` (S): Alert lifecycle state (`"SENT"` | `"ACKNOWLEDGED"`).
- **Primary Access Patterns**:
  - **Get Patient Alerts**: `Query(PK="P001", ScanIndexForward=False)` -> Displays emergency alert history badge on Doctor Dashboard.

---

### 5. `Documents` Table (Existing S3 Metadata Table)
- **Primary Key**:
  - **Partition Key (HASH)**: `DocumentId` (String, UUID v4)
- **Global Secondary Index (GSI)**:
  - **Index Name**: `PatientIdIndex`
  - **Partition Key (HASH)**: `PatientId` (String)
  - **Projection**: `ALL`
- **Billing Mode**: `PAY_PER_REQUEST`
- **Attributes**:
  - `DocumentId` (S): Unique document identifier.
  - `PatientId` (S): Associated patient ID.
  - `Filename` (S): Original uploaded file name (e.g. `"ECG_Report_P001.pdf"`).
  - `S3Key` (S): S3 bucket object key path (e.g. `"P001/uuid_ECG_Report_P001.pdf"`).
- **Primary Access Patterns**:
  - **List Patient Documents**: `Query(IndexName="PatientIdIndex", PK="P001")` -> Lists attached files for patient.
  - **Delete Document**: `DeleteItem(PK=DocumentId)` -> Removes document metadata.

---

## Access Pattern Matrix & Query Performance

| Access Pattern | Target Table / Index | Key Condition | Scan / Query | Target Latency |
| :--- | :--- | :--- | :--- | :--- |
| **Get Patient Demographics** | `Patients` | `PK = PatientId` | GetItem | < 5 ms |
| **Get Latest Vitals** | `VitalReadings` | `PK = PatientId` (ScanIndexForward=False, Limit=1) | Query | < 8 ms |
| **Fetch Vital Trend Line (Charts)** | `VitalReadings` | `PK = PatientId AND SK BETWEEN :t1 AND :t2` | Query | < 12 ms |
| **Fetch Current Health Risk** | `RiskAssessments` | `PK = PatientId` (ScanIndexForward=False, Limit=1) | Query | < 8 ms |
| **List Emergency Alerts** | `Alerts` | `PK = PatientId` | Query | < 10 ms |
| **List Medical Documents** | `Documents` / `PatientIdIndex` | `GSI PK = PatientId` | Query | < 10 ms |

---

## Viva Examination Defense Notes

> [!TIP]
> **Key Viva Question: Why use a Composite Primary Key (Partition Key + Sort Key) for `VitalReadings` instead of auto-increment IDs?**
> - **Answer**: In DynamoDB, composite keys enable efficient 1-to-N relationships and time-series ordering without expensive scans. By using `PatientId` as the Partition Key (HASH), all vital readings for a single patient are co-located in the same physical storage partition. By using `Timestamp` (ISO-8601 string) as the Sort Key (RANGE), DynamoDB automatically stores telemetry items in chronological order, allowing us to perform fast, low-cost time-range queries (`BETWEEN :t1 AND :t2`) or fetch the latest reading instantly using `ScanIndexForward=False, Limit=1`.

> [!TIP]
> **Key Viva Question: Why use PAY_PER_REQUEST (On-Demand) instead of Provisioned Capacity?**
> - **Answer**: Healthcare monitoring telemetry for a college prototype experiences unpredictable traffic spikes (e.g., when a simulator is executed or physical sensor transmits). `PAY_PER_REQUEST` eliminates the need for capacity planning, automatically scales up or down instantly to handle traffic bursts, and charges strictly per read/write request ($0 cost when no telemetry is arriving), making it ideal for cost control and academic demonstrations.

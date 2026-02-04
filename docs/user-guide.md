# User Guide

This guide covers the main features of this stock management system for Drosophila research labs.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Managing Stocks](#managing-stocks)
3. [Importing Stocks from BDSC](#importing-stocks-from-bdsc)
4. [Importing from CSV/Excel](#importing-from-csvexcel)
5. [Tags and Organization](#tags-and-organization)
6. [Cross Planning](#cross-planning)
7. [Labels and QR Codes](#labels-and-qr-codes)
8. [Admin Functions](#admin-functions)

---

## Getting Started

### Creating an Account

1. Navigate to the registration page at `/register`
2. Enter your email, password, and full name
3. Create a new organization name for your lab, or use an invitation link to join an existing lab
4. Wait for admin approval (if joining an existing organization)

### Dashboard Overview

After logging in, you'll see the dashboard with:
- **Total Stocks**: Number of active stocks in your collection
- **Active Crosses**: Planned or in-progress crosses
- **Tags**: Number of tags you've created
- Quick links to common actions

---

## Managing Stocks

### Viewing Stocks

Navigate to **Stocks** in the sidebar to see your stock collection. You can:
- **Search**: Use the search bar to find stocks by ID or genotype
- **Filter**: Filter by tags, source, or location
- **Sort**: Click column headers to sort

### Adding a New Stock

1. Click **Add Stock** button
2. Fill in the required fields:
   - **Stock ID**: A unique identifier (e.g., "BL-1234", "lab-001")
   - **Genotype**: The full genotype string
3. Optional fields:
   - **Source**: Where the stock came from (e.g., "Bloomington", "Gift from Smith Lab")
   - **Location**: Physical location (e.g., "Rack A, Shelf 2")
   - **Notes**: Any additional information
   - **Tags**: Select existing tags or create new ones
4. Click **Save**

### Editing a Stock

1. Click on a stock to view its details
2. Click **Edit** button
3. Modify the fields as needed
4. Click **Save**

### Deleting a Stock

Stocks are "soft deleted" - they're hidden but not permanently removed.

1. View the stock details
2. Click **Delete** button
3. Confirm the deletion

To restore a deleted stock, contact an admin or use the API.

---

## Importing Stocks from BDSC

The application can import stocks directly from the **Bloomington Drosophila Stock Center (BDSC)** database, which contains over 90,000 stocks.

### How It Works

Stock data is sourced from [FlyBase](https://flybase.org/) bulk data files, which are automatically downloaded and cached. This means:
- **Fast searches**: Data is stored locally for instant search results
- **Works offline**: After initial download, searches work without internet
- **Always current**: Data is refreshed periodically from FlyBase releases

### Importing Stocks

1. Navigate to **Import from BDSC** in the sidebar
2. **Search** for stocks:
   - Enter a BDSC stock number (e.g., `80563`) for exact matches
   - Enter genotype text (e.g., `GAL4`) to search within genotypes
3. **Review results**: Each result shows:
   - Stock number
   - Genotype
   - Species
   - Links to FlyBase and BDSC pages
4. **Select stocks** to import using the checkboxes
   - Use the header checkbox to select/deselect all
5. Click **Import Selected**

### What Gets Imported

When you import a BDSC stock, the system creates a new stock with:

| Field | Value |
|-------|-------|
| Stock ID | `BDSC-{stock_number}` (e.g., BDSC-80563) |
| Genotype | From FlyBase database |
| Source | `BDSC ({stock_number})` |
| External Metadata | FlyBase ID, URLs, import timestamp |

### Avoiding Duplicates

- If a stock with the same Stock ID already exists, it will be skipped
- The import results show how many were imported, skipped, or had errors

### External Links

Imported stocks include links to:
- **FlyBase**: Full stock report with references, phenotypes, etc.
- **BDSC**: Original BDSC page for ordering

---

## Importing from CSV/Excel

For bulk imports from your own data or other sources:

1. Navigate to **Import CSV** in the sidebar
2. **Download the template** to see the expected format
3. Fill in your data:
   - `stock_id` (required): Unique identifier
   - `genotype` (required): Full genotype string
   - `source` (optional): Origin of the stock
   - `location` (optional): Physical location
   - `notes` (optional): Additional notes
4. **Upload your file** (CSV or Excel format)
5. Review the import results

### CSV Format Example

```csv
stock_id,genotype,source,location,notes
BL-001,w[1118],Bloomington,Rack A,Canton-S background
BL-002,y[1] w[67c23],Bloomington,Rack A,Yellow white
custom-001,w; UAS-GFP/CyO,Gift from Lab,Rack B,GFP reporter
```

---

## Tags and Organization

Tags help you organize and filter your stock collection.

### Creating Tags

1. When adding/editing a stock, type a new tag name
2. Or go to the Tags section (if available in your version)
3. Choose a color for visual identification

### Using Tags

- Click a tag to filter stocks
- Stocks can have multiple tags
- Tags are shared across your organization

### Tag Ideas

- **By project**: "Screen 2024", "Aging Study"
- **By chromosome**: "X", "2L", "3R"
- **By type**: "Balancer", "Driver", "Reporter"
- **By status**: "Active", "Archive", "Needs expansion"

---

## Cross Planning

Plan and track genetic crosses between stocks.

### Creating a Cross

1. Navigate to **Crosses** in the sidebar
2. Click **Plan Cross**
3. Select:
   - **Female parent**: Stock providing females
   - **Male parent**: Stock providing males
4. Optionally add:
   - **Name**: Descriptive name for the cross
   - **Planned date**: When you intend to set up the cross
   - **Notes**: Expected outcomes, purpose, etc.
5. Click **Save**

### Cross Workflow

1. **Planned**: Initial state after creation
2. **In Progress**: Click "Start" when you set up the cross
3. **Completed**: Click "Complete" and optionally link to offspring stock
4. **Failed**: Click "Fail" if the cross didn't work

### Viewing Cross History

- See all crosses in the Crosses list
- Filter by status (Planned, In Progress, Completed, Failed)
- Click a cross to see full details and history

---

## Labels and QR Codes

Generate labels for your vials with QR codes or barcodes.

### Generating Labels

1. View a stock's detail page
2. Click **Print Label** or navigate to Labels section
3. Choose format:
   - **QR Code**: Scannable code linking to stock details
   - **Barcode**: Traditional barcode with stock ID
4. Print or download the label

### Scanning Labels

Use any QR code scanner (phone camera, dedicated scanner) to quickly access stock details.

---

## Admin Functions

*Requires admin role*

### User Management

1. Navigate to **Admin** in the sidebar
2. View pending user registrations
3. **Approve** or **Reject** new users
4. Change user roles (Admin/User)
5. Deactivate users who have left

### Organization Settings

- Update organization name
- Generate invitation links for new users
- View organization statistics

### Invitation Links

1. Go to Admin > Organization
2. Click **Generate Invitation Link**
3. Share the link with new lab members
4. They can register directly without waiting for approval

---

## Tips and Best Practices

### Naming Conventions

Establish consistent stock ID patterns:
- `BDSC-{number}` for Bloomington stocks
- `VDRC-{number}` for Vienna stocks
- `{initials}-{number}` for lab-generated stocks

### Regular Maintenance

- Archive stocks you no longer maintain
- Update locations when reorganizing
- Tag stocks by project for easy filtering

### Data Backup

- Use the CSV export feature regularly
- Your admin can request full database exports

---

## Getting Help

- Check the documentation at `/docs`
- Contact your lab admin for organization-specific questions
- Report bugs or feature requests on GitHub

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `/` | Focus search bar |
| `n` | New stock (on stocks page) |
| `Esc` | Close modal/cancel |

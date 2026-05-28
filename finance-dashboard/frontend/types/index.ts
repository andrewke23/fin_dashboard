export interface Account {
    id: string;
    institution_id: string;
    plaid_account_id: string;
    name: string;
    mask?: string;
    subtype?: string;
    current_balance: number;
    available_balance?: number;
    is_active: boolean;
    // UPGRADED: Now it is an array of ruleset objects!
    reward_rules?: {
      effective_date: string;
      base: number;
      categories: Record<string, number>;
    }[];
  }
  
  export interface Institution {
    id: string;
    institution_name: string;
    accounts: Account[];
    last_sync: string | null;
  }
  
  export interface Transaction {
    id: string;
    account_id: string;
    merchant_name?: string;
    name: string;
    amount: number;
    category?: string;
    date: string;
    pending: boolean;
    points_earned: number;  
  }
  
  export interface PaginatedTransactions {
    transactions: Transaction[];
    total: number;
    page: number;
    page_size: number;
    total_pages: number;
  }
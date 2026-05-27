'use client';

import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  createColumnHelper,
} from '@tanstack/react-table';
import { Transaction, PaginatedTransactions, Institution } from '@/types';
import { getInstitutions } from '@/lib/api';

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ChevronLeft, ChevronRight, Search, SlidersHorizontal, X } from 'lucide-react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { updateTransactionCategory } from '@/lib/api';
import MonthlySpendingChart from '@/components/charts/MonthlySpendingChart';
import CategoryPieChart from '@/components/charts/CategoryPieChart';

const columnHelper = createColumnHelper<Transaction>();

export default function TransactionsPage() {
  // ── State Management for Filters & Pagination ────────────────────────────
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [accountId, setAccountId] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all'); // all, posted, pending
  const pageSize = 25;

  // ── Fetch Structural Metadata (For Account Dropdown Filter) ──────────────
  const { data: institutions } = useQuery<Institution[]>({
    queryKey: ['institutions'],
    queryFn: getInstitutions,
  });

  // Flatten accounts array for straightforward access in filter mapping
  const allAccounts = institutions?.flatMap((inst) => inst.accounts) || [];

  // ── Fetch Paginated, Filtered Transactions ────────────────────────────────
  const { data, isLoading, isPlaceholderData } = useQuery<PaginatedTransactions>({
    queryKey: ['transactions', page, search, accountId, statusFilter],
    queryFn: async () => {
      const params: Record<string, unknown> = {
        page,
        page_size: pageSize,
        sort_by: 'date',
        sort_dir: 'desc',
      };
      if (search) params.search = search;
      if (accountId !== 'all') params.account_id = accountId;
      if (statusFilter === 'pending') params.pending = true;
      if (statusFilter === 'posted') params.pending = false;

      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
      const response = await axios.get(`${apiUrl}/transactions`, { params });
      return response.data;
    },
    placeholderData: (previousData) => previousData, // Smooth pagination transition
  });

  // ── Table Columns Definitions ─────────────────────────────────────────────
  const columns = [
    columnHelper.accessor('date', {
      header: 'Date',
      cell: (info) => <span className="font-mono text-muted-foreground">{info.getValue()}</span>,
    }),
    columnHelper.accessor((row) => row.merchant_name || row.name, {
      id: 'merchant',
      header: 'Description',
      cell: (info) => (
        <div className="font-medium max-w-[280px] truncate">
          {info.getValue()}
        </div>
      ),
    }),
    columnHelper.accessor('category', {
        header: 'Category',
        cell: (info) => {
          // Grab the row's specific data
          const currentCategory = info.getValue() || 'Uncategorized';
          const transactionId = info.row.original.id;
          
          // eslint-disable-next-line react-hooks/rules-of-hooks
          const queryClient = useQueryClient();
  
          // Setup the background save mutation
          // eslint-disable-next-line react-hooks/rules-of-hooks
          const categoryMutation = useMutation({
            mutationFn: (newCategory: string) => updateTransactionCategory(transactionId, newCategory),
            onSuccess: () => {
              // Silently refresh the table data to confirm the save
              queryClient.invalidateQueries({ queryKey: ['transactions'] });
            },
          });
  
          // A standardized list of categories for the dropdown
          const standardCategories = [
            "Income", "Food and Drink", "Transportation", "Shopping", 
            "Entertainment", "Bills and Utilities", "Travel", 
            "Personal Care", "Transfer", "Uncategorized"
          ];
  
          // Format Plaid's loud "FOOD_AND_DRINK" strings into title case for display
          const displayValue = currentCategory.replace(/_/g, ' ').toLowerCase();
  
          return (
            <div className="flex items-center" onClick={(e) => e.stopPropagation()}>
              <Select 
                defaultValue={currentCategory} 
                onValueChange={(val) => categoryMutation.mutate(val)}
                disabled={categoryMutation.isPending}
              >
                <SelectTrigger className={`h-6 w-auto px-2.5 py-0 border-none rounded-full text-xs font-medium focus:ring-0 focus:ring-offset-0 shadow-none transition-colors ${categoryMutation.isPending ? 'opacity-50' : 'bg-secondary text-secondary-foreground hover:bg-secondary/80'}`}>
                  <SelectValue placeholder="Select category">
                    <span className="capitalize">{displayValue}</span>
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {standardCategories.map((cat) => (
                    <SelectItem key={cat} value={cat.toUpperCase().replace(/ /g, '_')} className="text-xs">
                      {cat}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          );
        },
      }),
    columnHelper.accessor('account_id', {
      header: 'Account',
      cell: (info) => {
        const accId = info.getValue();
        const matchedAcc = allAccounts.find((a) => a.id === accId);
        return matchedAcc ? (
          <span className="text-xs font-medium text-muted-foreground">
            {matchedAcc.name} {matchedAcc.mask ? `(..${matchedAcc.mask})` : ''}
          </span>
        ) : (
          <span className="text-xs text-muted-foreground font-mono">Account</span>
        );
      },
    }),
    columnHelper.accessor('pending', {
      header: 'Status',
      cell: (info) => info.getValue() ? (
        <Badge variant="outline" className="text-amber-500 border-amber-500/30 bg-amber-500/5">Pending</Badge>
      ) : (
        <Badge variant="outline" className="text-emerald-500 border-emerald-500/30 bg-emerald-500/5">Posted</Badge>
      ),
    }),
    columnHelper.accessor('points_earned', {
        header: () => <div className="text-right text-purple-500">Points</div>,
        cell: (info) => {
          const points = info.getValue() || 0;
          // Only show points for purchases, not for paying off the credit card (credits)
          if (points === 0) return <div className="text-right text-muted-foreground">-</div>;
          
          return (
            <div className="text-right font-semibold font-mono text-purple-500">
              +{points.toLocaleString()}
            </div>
          );
        },
      }),
    columnHelper.accessor('amount', {
      header: () => <div className="text-right">Amount</div>,
      cell: (info) => {
        const amount = info.getValue();
        // Plaid syntax: Positive number = Outflow/Debit, Negative number = Inflow/Credit
        const isCredit = amount < 0;
        return (
          <div className={`text-right font-semibold font-mono ${isCredit ? 'text-emerald-500' : 'text-foreground'}`}>
            {isCredit ? `-` : ''}${Math.abs(amount).toFixed(2)}
          </div>
        );
      },
    }),
  ];

  // Initialize TanStack Table core state mapping
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data: data?.transactions || [],
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  const clearFilters = () => {
    setSearch('');
    setAccountId('all');
    setStatusFilter('all');
    setPage(1);
  };

  const hasActiveFilters = search !== '' || accountId !== 'all' || statusFilter !== 'all';

  return (
    <div className="space-y-6">
      {/* Page Heading */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Transactions</h1>
        <p className="text-muted-foreground mt-1">Review, look up, and filter full local transaction histories.</p>
      </div>

      {/* Control / Filter Bar Layout */}
      <Card className="border-muted/40 bg-card/50 backdrop-blur-sm">
        <CardContent className="pt-6 gap-4 flex flex-col md:flex-row items-stretch md:items-center justify-between">
          
          {/* Left Controls: Input Searching and Dropdowns */}
          <div className="flex flex-1 flex-wrap items-center gap-3">
            <div className="relative w-full md:w-72">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search description or merchant..."
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setPage(1); // Reset page on filter shift
                }}
                className="w-full bg-background border border-input rounded-md pl-9 pr-4 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              />
            </div>

            {/* Account Selector filter */}
            <Select value={accountId} onValueChange={(val) => { setAccountId(val); setPage(1); }}>
              <SelectTrigger className="w-full md:w-[200px] bg-background">
                <SlidersHorizontal className="mr-2 h-3.5 w-3.5 text-muted-foreground" />
                <SelectValue placeholder="All Accounts" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Accounts</SelectItem>
                {allAccounts.map((acc) => (
                  <SelectItem key={acc.id} value={acc.id}>
                    {acc.name} {acc.mask ? `(..${acc.mask})` : ''}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* Status Selector filter */}
            <Select value={statusFilter} onValueChange={(val) => { setStatusFilter(val); setPage(1); }}>
              <SelectTrigger className="w-full md:w-[140px] bg-background">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                <SelectItem value="posted">Posted Only</SelectItem>
                <SelectItem value="pending">Pending Only</SelectItem>
              </SelectContent>
            </Select>

            {hasActiveFilters && (
              <Button variant="ghost" onClick={clearFilters} className="text-xs h-9 px-2 text-muted-foreground">
                <X className="mr-1 h-3 w-3" /> Clear Filters
              </Button>
            )}
          </div>
          
          {/* Right Controls: Meta Info Panel */}
          <div className="text-xs text-muted-foreground text-right font-mono self-end md:self-center">
            Found {data?.total || 0} items
          </div>
        </CardContent>
      </Card>

      {/* Main Table Interface */}
      <div className="rounded-md border border-muted/40 bg-background overflow-hidden">
        <Table>
          <TableHeader className="bg-muted/30">
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead key={header.id}>
                    {header.isPlaceholder
                      ? null
                      : flexRender(header.column.columnDef.header, header.getContext())}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={columns.length} className="h-32 text-center text-sm text-muted-foreground">
                  Querying database ledger...
                </TableCell>
              </TableRow>
            ) : table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow key={row.id} className="hover:bg-muted/20 border-b border-muted/30 transition-colors">
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id} className="py-3">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={columns.length} className="h-32 text-center text-sm text-muted-foreground">
                  No matching transaction history matches found.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination Interface Footer */}
      {data && data.total_pages > 1 && (
        <div className="flex items-center justify-between py-2">
          <div className="text-sm text-muted-foreground font-mono">
            Page {page} of {data.total_pages}
          </div>
          <div className="flex items-center space-x-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((old) => Math.max(old - 1, 1))}
              disabled={page === 1 || isLoading}
              className="h-8 w-8 p-0"
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                if (!isPlaceholderData && page < data.total_pages) {
                  setPage((old) => old + 1);
                }
              }}
              disabled={isPlaceholderData || page >= data.total_pages || isLoading}
              className="h-8 w-8 p-0"
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
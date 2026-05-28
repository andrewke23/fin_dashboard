'use client';

import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getInstitutions, updateRewardRules } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Plus, Trash2, Save, Edit2, Loader2, Award, Calendar } from 'lucide-react';
import { Institution, Account } from '@/types';

const STANDARD_CATEGORIES = [
  "FOOD_AND_DRINK", "TRAVEL", "TRANSPORTATION", 
  "GENERAL_MERCHANDISE", "ENTERTAINMENT", "PERSONAL_CARE", 
  "BILLS_AND_UTILITIES", "SHOPPING"
];

export default function RewardRulesEditor() {
  const queryClient = useQueryClient();
  const [selectedAccountId, setSelectedAccountId] = useState<string>('');
  const [baseMultiplier, setBaseMultiplier] = useState<number>(1.0);
  const [categories, setCategories] = useState<{ category: string; multiplier: number }[]>([]);
  const [isEditing, setIsEditing] = useState<boolean>(false);

  // Fetch accounts
  const { data: institutions, isLoading } = useQuery<Institution[]>({
    queryKey: ['institutions'],
    queryFn: getInstitutions,
  });

  const flatAccounts = institutions?.flatMap(inst => inst.accounts) || [];
  const selectedAccount = flatAccounts.find(a => a.id === selectedAccountId);

  // Handle dropdown selection change
  const handleAccountChange = (accountId: string) => {
    setSelectedAccountId(accountId);
    setIsEditing(false); // Default to read-only summary view when switching cards
    
    const account = flatAccounts.find(a => a.id === accountId);
    if (account) {
      // Look for the first/active ruleset array item or fall back
      const rulesArray = account.reward_rules || [];
      const primaryRuleset = rulesArray[0] || { base: 1.0, categories: {} };
      
      setBaseMultiplier(primaryRuleset.base || 1.0);
      
      const catsArray = Object.entries(primaryRuleset.categories || {}).map(([key, val]) => ({
        category: key,
        multiplier: Number(val),
      }));
      setCategories(catsArray);
    }
  };

  // Save Mutation
  const saveMutation = useMutation({
    mutationFn: (accountId: string) => {
      const categoriesObj: Record<string, number> = {};
      categories.forEach(c => {
        if (c.category) categoriesObj[c.category] = Number(c.multiplier);
      });

      // FIX: Wrap the ruleset inside an array to perfectly match the backend's List[RewardRulePeriod]
      const payload = [
        {
          effective_date: "1970-01-01", 
          base: Number(baseMultiplier),
          categories: categoriesObj,
        }
      ];
      
      return updateRewardRules(accountId, payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['institutions'] });
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['points_by_month'] });
      setIsEditing(false); // Smoothly exit edit mode back to view summary mode
    }
  });

  if (isLoading) return <div className="text-sm text-muted-foreground">Loading accounts...</div>;

  return (
    <Card className="col-span-full md:col-span-1 border-muted/40 bg-card/50 backdrop-blur-sm">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Award className="h-5 w-5 text-purple-500" />
          Card Rules Engine
        </CardTitle>
        <CardDescription>Manage multipliers and timeline point structures.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        
        {/* Account Selector Dropdown */}
        <div className="space-y-2">
          <label className="text-xs font-semibold text-muted-foreground">Select Card</label>
          <Select value={selectedAccountId} onValueChange={handleAccountChange}>
            <SelectTrigger className="w-full bg-background">
              <SelectValue placeholder="Choose a credit card..." />
            </SelectTrigger>
            <SelectContent>
              {flatAccounts.map((acc: Account) => (
                <SelectItem key={acc.id} value={acc.id}>
                  {acc.name} {acc.mask ? `(..${acc.mask})` : ''}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {selectedAccountId && (
          <div className="pt-4 border-t border-muted/30">
            
            {/* ── MODE 1: READ-ONLY SAVED STATE SUMMARY ──────────────────────── */}
            {!isEditing ? (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="text-sm font-semibold">Active Ruleset</h4>
                    <p className="text-xs text-muted-foreground flex items-center gap-1 mt-0.5">
                      <Calendar className="h-3 w-3" /> Effective since account opening
                    </p>
                  </div>
                  <Button 
                    variant="outline" 
                    size="sm" 
                    className="h-8 text-xs"
                    onClick={() => {
                      // Ensure the form state is perfectly synced with the DB before editing
                      const rulesArray = selectedAccount?.reward_rules || [];
                      const primaryRuleset = rulesArray[0] || { base: 1.0, categories: {} };
                      setBaseMultiplier(primaryRuleset.base || 1.0);
                      setCategories(Object.entries(primaryRuleset.categories || {}).map(([key, val]) => ({
                        category: key,
                        multiplier: Number(val),
                      })));
                      setIsEditing(true);
                    }}
                  >
                    <Edit2 className="h-3 w-3 mr-1" /> Edit Rules
                  </Button>
                </div>

                <div className="rounded-lg bg-muted/30 p-3 space-y-2 text-sm border border-muted/20">
                  <div className="flex justify-between border-b border-muted/30 pb-1.5 text-xs font-semibold text-muted-foreground">
                    <span>Category</span>
                    <span>Multiplier</span>
                  </div>
                  
                  {/* Read directly from the selectedAccount (the database truth), not local state */}
                  <div className="flex justify-between py-0.5 font-medium">
                    <span>Base Rate (All spending)</span>
                    <span className="font-mono text-purple-500">
                      {(selectedAccount?.reward_rules?.[0]?.base || 1.0).toFixed(1)}x
                    </span>
                  </div>
                  
                  {Object.entries(selectedAccount?.reward_rules?.[0]?.categories || {}).map(([cat, mult]) => (
                    <div key={cat} className="flex justify-between py-0.5">
                      <span className="capitalize text-muted-foreground">{cat.replace(/_/g, ' ').toLowerCase()}</span>
                      <span className="font-mono font-semibold text-purple-500">{Number(mult).toFixed(1)}x</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              
              /* ── MODE 2: INTERACTIVE EDIT MODE FORM ────────────────────────── */
              <div className="space-y-6">
                {/* Base Multiplier input */}
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Base Multiplier</span>
                  <div className="flex items-center space-x-2">
                    <input 
                      type="number" 
                      step="0.1"
                      value={baseMultiplier}
                      onChange={(e) => setBaseMultiplier(parseFloat(e.target.value) || 0)}
                      className="w-20 bg-background border border-input rounded-md px-3 py-1 text-sm text-right focus:outline-none focus:ring-1 focus:ring-ring font-mono"
                    />
                    <span className="text-sm text-muted-foreground font-mono">x</span>
                  </div>
                </div>

                {/* Category Rule Builder array items */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Category Overrides</span>
                    <Button 
                      variant="outline" 
                      size="sm" 
                      className="h-7 text-xs border-dashed"
                      onClick={() => setCategories([...categories, { category: STANDARD_CATEGORIES[0], multiplier: 2.0 }])}
                    >
                      <Plus className="h-3 w-3 mr-1" /> Add Category
                    </Button>
                  </div>

                  {categories.map((cat, index) => (
                    <div key={index} className="flex items-center space-x-2">
                      <Select 
                        value={cat.category} 
                        onValueChange={(val) => {
                          const newCats = [...categories];
                          newCats[index].category = val;
                          setCategories(newCats);
                        }}
                      >
                        <SelectTrigger className="flex-1 h-9 bg-background">
                          <SelectValue placeholder="Select Category" />
                        </SelectTrigger>
                        <SelectContent>
                          {STANDARD_CATEGORIES.map(c => (
                            <SelectItem key={c} value={c} className="text-xs">{c.replace(/_/g, ' ')}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      
                      <input 
                        type="number" 
                        step="0.1"
                        value={cat.multiplier}
                        onChange={(e) => {
                          const newCats = [...categories];
                          newCats[index].multiplier = parseFloat(e.target.value) || 0;
                          setCategories(newCats);
                        }}
                        className="w-16 h-9 bg-background border border-input rounded-md px-2 text-sm text-right focus:outline-none focus:ring-1 focus:ring-ring font-mono"
                      />
                      <span className="text-sm text-muted-foreground font-mono pr-1">x</span>

                      <Button 
                        variant="ghost" 
                        size="icon" 
                        className="h-9 w-9 text-muted-foreground hover:text-red-500 hover:bg-red-500/10"
                        onClick={() => setCategories(categories.filter((_, i) => i !== index))}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>

                {/* Submit actions buttons group */}
                <div className="flex gap-2 pt-2">
                  <Button 
                    variant="ghost"
                    className="flex-1 text-xs"
                    disabled={saveMutation.isPending}
                    onClick={() => handleAccountChange(selectedAccountId)} // Reverts form state to saved database state
                  >
                    Cancel
                  </Button>
                  <Button 
                    className="flex-1 text-xs" 
                    disabled={saveMutation.isPending}
                    onClick={() => saveMutation.mutate(selectedAccountId)}
                  >
                    {saveMutation.isPending ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Save className="mr-2 h-4 w-4" />
                    )}
                    Save Ruleset
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
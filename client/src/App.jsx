import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table"
import {
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  Download,
  ExternalLink,
  Filter,
  MapPin,
  RefreshCcw,
  Search,
} from "lucide-react"

import { Button } from "@/components/ui/button"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api"
const ALL_VALUE = "all"

async function fetchJson(path) {
  const response = await fetch(`${API_BASE_URL}${path}`)
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  return response.json()
}

const formatCurrency = (value) => {
  if (value === null || value === undefined) return "P.O.A"
  return new Intl.NumberFormat("en-AU", {
    style: "currency",
    currency: "AUD",
    maximumFractionDigits: 0,
  }).format(value)
}

const formatDate = (value) => {
  if (!value) return "Unknown"
  return new Intl.DateTimeFormat("en-AU", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value))
}

const formatOpportunityType = (value) =>
  (value || "Unknown").replaceAll("_", " ").replace("Franchise New", "Franchise new")

const buildListingsPath = ({ category, state, opportunityType, search }) => {
  const params = new URLSearchParams({
    limit: "500",
    sort: "refresh_date",
    direction: "desc",
  })

  if (category !== ALL_VALUE) params.set("category", category)
  if (state !== ALL_VALUE) params.set("state", state)
  if (opportunityType !== ALL_VALUE) params.set("opportunity_type", opportunityType)
  if (search.trim()) params.set("search", search.trim())

  return `/listings?${params.toString()}`
}

function SortButton({ column, children }) {
  return (
    <button
      type="button"
      className="inline-flex items-center gap-1 text-left font-medium text-neutral-700 transition hover:text-neutral-950"
      onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
    >
      {children}
      <ArrowUpDown className="size-3.5 text-neutral-400" aria-hidden="true" />
    </button>
  )
}

function SelectFilter({ label, value, onChange, options }) {
  return (
    <label className="grid gap-1.5 text-sm">
      <span className="font-medium text-neutral-700">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-10 rounded-md border border-neutral-200 bg-white px-3 text-sm outline-none transition focus:border-neutral-400 focus:ring-3 focus:ring-neutral-200"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  )
}

function App() {
  const queryClient = useQueryClient()
  const [category, setCategory] = useState(ALL_VALUE)
  const [state, setState] = useState(ALL_VALUE)
  const [opportunityType, setOpportunityType] = useState(ALL_VALUE)
  const [search, setSearch] = useState("")

  const categoriesQuery = useQuery({
    queryKey: ["categories"],
    queryFn: () => fetchJson("/categories"),
  })

  const summaryQuery = useQuery({
    queryKey: ["categories-summary"],
    queryFn: () => fetchJson("/categories/summary"),
  })

  const absQuery = useQuery({
    queryKey: ["abs-releases"],
    queryFn: () => fetchJson("/abs/releases"),
  })

  const absScrapeMutation = useMutation({
    mutationFn: async () => {
      const response = await fetch(`${API_BASE_URL}/abs/scrape`, { method: "POST" })
      if (!response.ok) {
        throw new Error(`ABS scrape failed: ${response.status}`)
      }
      return response.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["abs-releases"] })
    },
  })

  const listingsPath = buildListingsPath({ category, state, opportunityType, search })
  const listingsQuery = useQuery({
    queryKey: ["listings", category, state, opportunityType, search],
    queryFn: () => fetchJson(listingsPath),
  })

  const data = useMemo(() => listingsQuery.data?.data ?? [], [listingsQuery.data])
  const total = listingsQuery.data?.total ?? 0
  const categories = categoriesQuery.data?.data ?? []
  const categorySummary = summaryQuery.data?.data ?? []
  const absSummary = absQuery.data

  const states = useMemo(
    () =>
      Array.from(new Set(data.map((item) => item.state).filter(Boolean))).sort((a, b) =>
        a.localeCompare(b),
      ),
    [data],
  )

  const opportunityTypes = useMemo(
    () =>
      Array.from(new Set(data.map((item) => item.opportunity_type).filter(Boolean))).sort((a, b) =>
        a.localeCompare(b),
      ),
    [data],
  )

  const columns = useMemo(
    () => [
      {
        accessorKey: "title",
        header: ({ column }) => <SortButton column={column}>Opportunity</SortButton>,
        cell: ({ row }) => (
          <div className="max-w-[360px]">
            <a
              className="font-medium text-neutral-950 underline-offset-3 hover:underline"
              href={row.original.url}
              target="_blank"
              rel="noreferrer"
            >
              {row.original.title}
            </a>
            <div className="mt-1 line-clamp-2 text-xs leading-5 text-neutral-500">
              {row.original.summary || row.original.business_name || "No summary captured"}
            </div>
          </div>
        ),
      },
      {
        accessorKey: "category",
        header: ({ column }) => <SortButton column={column}>Category</SortButton>,
        cell: ({ row }) => (
          <div>
            <div className="font-medium text-neutral-800">{row.original.category}</div>
            <div className="text-xs text-neutral-500">{row.original.industry}</div>
          </div>
        ),
      },
      {
        accessorKey: "location",
        header: ({ column }) => <SortButton column={column}>Location</SortButton>,
        cell: ({ row }) => (
          <span className="inline-flex max-w-[210px] items-center gap-1.5">
            <MapPin className="size-3.5 shrink-0 text-neutral-400" aria-hidden="true" />
            <span>
              {row.original.location}
              {row.original.state ? `, ${row.original.state}` : ""}
            </span>
          </span>
        ),
      },
      {
        accessorKey: "price_min",
        header: ({ column }) => <SortButton column={column}>Investment</SortButton>,
        cell: ({ row }) => {
          const min = row.original.price_min
          const max = row.original.price_max
          const price =
            min && max && min !== max
              ? `${formatCurrency(min)} - ${formatCurrency(max)}`
              : formatCurrency(min)

          return (
            <div>
              <div className="font-medium text-neutral-900">{price}</div>
              <div className="text-xs text-neutral-500">
                {[
                  row.original.is_poa ? "P.O.A" : null,
                  row.original.has_sav ? "+ SAV" : null,
                  row.original.is_negotiable ? "Negotiable" : null,
                ]
                  .filter(Boolean)
                  .join(" / ") || "Listed range"}
              </div>
            </div>
          )
        },
      },
      {
        accessorKey: "opportunity_type",
        header: "Type",
        cell: ({ getValue }) => (
          <span className="rounded-md border border-neutral-200 px-2 py-1 text-xs text-neutral-700">
            {formatOpportunityType(getValue())}
          </span>
        ),
      },
      {
        accessorKey: "business_name",
        header: ({ column }) => <SortButton column={column}>Advertiser</SortButton>,
        cell: ({ row }) => (
          <span className="inline-flex max-w-[220px] items-center gap-1.5">
            <span>
              {row.original.business_name || "Unknown"}
              {row.original.client_type ? (
                <span className="block text-xs text-neutral-500">{row.original.client_type}</span>
              ) : null}
            </span>
            <ExternalLink className="size-3 shrink-0 text-neutral-400" aria-hidden="true" />
          </span>
        ),
      },
      {
        accessorKey: "refresh_date",
        header: ({ column }) => <SortButton column={column}>Freshness</SortButton>,
        cell: ({ getValue }) => (
          <span className="whitespace-nowrap text-neutral-700">{formatDate(getValue())}</span>
        ),
      },
    ],
    [],
  )

  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: {
      pagination: { pageSize: 12 },
      sorting: [{ id: "refresh_date", desc: true }],
    },
  })

  const categoryOptions = [
    { value: ALL_VALUE, label: "All categories" },
    ...categories.map((item) => ({
      value: item.url_key,
      label: `${item.name} (${item.stored_listings})`,
    })),
  ]

  const stateOptions = [
    { value: ALL_VALUE, label: "All states" },
    ...states.map((item) => ({ value: item, label: item })),
  ]

  const typeOptions = [
    { value: ALL_VALUE, label: "All types" },
    ...opportunityTypes.map((item) => ({
      value: item,
      label: formatOpportunityType(item),
    })),
  ]

  const isLoading =
    categoriesQuery.isLoading || summaryQuery.isLoading || listingsQuery.isLoading

  const resetFilters = () => {
    setCategory(ALL_VALUE)
    setState(ALL_VALUE)
    setOpportunityType(ALL_VALUE)
    setSearch("")
  }

  const exportCsv = () => {
    const headers = [
      "seek_id",
      "title",
      "category",
      "industry",
      "location",
      "state",
      "price_min",
      "price_max",
      "opportunity_type",
      "business_name",
      "refresh_date",
      "url",
    ]
    const rows = data.map((item) =>
      headers
        .map((header) => `"${String(item[header] ?? "").replaceAll('"', '""')}"`)
        .join(","),
    )
    const blob = new Blob([[headers.join(","), ...rows].join("\n")], {
      type: "text/csv;charset=utf-8",
    })
    const url = URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = url
    link.download = "seek-business-listings.csv"
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <main className="min-h-screen bg-neutral-50 text-neutral-950">
      <section className="border-b border-neutral-200 bg-white">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-5 px-5 py-5 sm:px-8 lg:px-10">
          <nav className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-2 font-semibold">
              <span className="flex size-8 items-center justify-center rounded-md bg-neutral-950 text-white">
                SB
              </span>
              SEEK Business Lens
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => absScrapeMutation.mutate()}
                disabled={absScrapeMutation.isPending}
              >
                <RefreshCcw />
                {absScrapeMutation.isPending ? "Refreshing ABS" : "Refresh ABS"}
              </Button>
              <Button variant="outline" size="sm" onClick={() => listingsQuery.refetch()}>
                <RefreshCcw />
                Refresh
              </Button>
              <Button variant="outline" size="sm" onClick={exportCsv} disabled={!data.length}>
                <Download />
                Export CSV
              </Button>
            </div>
          </nav>

        </div>
      </section>

      <section className="mx-auto w-full max-w-7xl px-5 py-6 sm:px-8 lg:px-10">
        <section>
          <div className="mb-4 rounded-lg border border-neutral-200 bg-white p-4">
            <div className="grid gap-4 lg:grid-cols-[1fr_180px_190px_auto] lg:items-end">
              <SelectFilter
                label="Category"
                value={category}
                onChange={(value) => {
                  setCategory(value)
                  setState(ALL_VALUE)
                  setOpportunityType(ALL_VALUE)
                }}
                options={categoryOptions}
              />
              <SelectFilter label="State" value={state} onChange={setState} options={stateOptions} />
              <SelectFilter
                label="Type"
                value={opportunityType}
                onChange={setOpportunityType}
                options={typeOptions}
              />
              <Button variant="outline" size="sm" onClick={resetFilters} className="h-10">
                Reset
              </Button>
            </div>

            <div className="mt-4 flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
              <div className="flex flex-wrap gap-2 text-xs text-neutral-500">
                {categorySummary.map((item) => (
                  <button
                    key={item.category_url_key}
                    type="button"
                    className={`rounded-md border px-2.5 py-1 transition ${
                      category === item.category_url_key
                        ? "border-neutral-950 bg-neutral-950 text-white"
                        : "border-neutral-200 bg-neutral-50 hover:border-neutral-300"
                    }`}
                    onClick={() => setCategory(item.category_url_key)}
                  >
                    {item.category} {item.listings}
                  </button>
                ))}
              </div>

              <label className="relative block w-full xl:max-w-sm">
              <Search
                className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-neutral-400"
                aria-hidden="true"
              />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search title, broker, industry, location..."
                className="h-10 w-full rounded-md border border-neutral-200 bg-white pl-9 pr-3 text-sm outline-none transition placeholder:text-neutral-400 focus:border-neutral-400 focus:ring-3 focus:ring-neutral-200"
              />
              </label>
            </div>
          </div>

          <div className="overflow-hidden rounded-lg border border-neutral-200 bg-white">
            <div className="flex items-center justify-between gap-3 border-b border-neutral-200 px-4 py-3 text-sm text-neutral-500">
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                <span className="inline-flex items-center gap-2">
                  <Filter className="size-4" aria-hidden="true" />
                  {table.getFilteredRowModel().rows.length.toLocaleString("en-AU")} loaded rows,
                  {total.toLocaleString("en-AU")} matching records
                </span>
                {absSummary ? (
                  <span>
                    ABS context: {absSummary.count} releases, {absSummary.table_count} tables
                  </span>
                ) : null}
              </div>
              {listingsQuery.isFetching ? <span>Updating...</span> : null}
            </div>

            <div className="overflow-x-auto">
              <table className="w-full min-w-[1180px] border-collapse text-sm">
                <thead className="bg-neutral-50 text-left text-xs uppercase text-neutral-500">
                  {table.getHeaderGroups().map((headerGroup) => (
                    <tr key={headerGroup.id}>
                      {headerGroup.headers.map((header) => (
                        <th key={header.id} className="px-4 py-3 font-medium">
                          {header.isPlaceholder
                            ? null
                            : flexRender(header.column.columnDef.header, header.getContext())}
                        </th>
                      ))}
                    </tr>
                  ))}
                </thead>
                <tbody>
                  {isLoading ? (
                    <tr>
                      <td className="px-4 py-10 text-center text-neutral-500" colSpan={columns.length}>
                        Loading listings...
                      </td>
                    </tr>
                  ) : table.getRowModel().rows.length ? (
                    table.getRowModel().rows.map((row) => (
                      <tr key={row.id} className="border-t border-neutral-100">
                        {row.getVisibleCells().map((cell) => (
                          <td key={cell.id} className="px-4 py-4 align-middle text-neutral-700">
                            {flexRender(cell.column.columnDef.cell, cell.getContext())}
                          </td>
                        ))}
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td className="px-4 py-10 text-center text-neutral-500" colSpan={columns.length}>
                        No listings match the current filters.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <div className="flex flex-col gap-3 border-t border-neutral-200 px-4 py-3 text-sm text-neutral-500 sm:flex-row sm:items-center sm:justify-between">
              <span>
                Page {table.getState().pagination.pageIndex + 1} of {table.getPageCount() || 1}
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => table.previousPage()}
                  disabled={!table.getCanPreviousPage()}
                >
                  <ChevronLeft />
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => table.nextPage()}
                  disabled={!table.getCanNextPage()}
                >
                  Next
                  <ChevronRight />
                </Button>
              </div>
            </div>
          </div>
        </section>
      </section>
    </main>
  )
}

export default App

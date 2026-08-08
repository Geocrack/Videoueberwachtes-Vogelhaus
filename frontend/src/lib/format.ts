const relative = new Intl.RelativeTimeFormat('de', { numeric: 'auto' })

const STEPS: Array<[Intl.RelativeTimeFormatUnit, number]> = [
    ['second', 60],
    ['minute', 60],
    ['hour', 24],
    ['day', 30],
    ['month', 12],
]

export function formatRelativeTime(isoTimestamp: string | null): string {
    if (isoTimestamp === null) return 'noch nie'

    const timestamp = new Date(isoTimestamp).getTime()
    if (Number.isNaN(timestamp)) return 'unbekannt'

    let amount = Math.round((timestamp - Date.now()) / 1000)
    for (const [unit, size] of STEPS) {
        if (Math.abs(amount) < size) return relative.format(amount, unit)
        amount = Math.round(amount / size)
    }

    return relative.format(amount, 'year')
}

export function formatCount(value: number, singular: string, plural: string) {
    return `${value} ${value === 1 ? singular : plural}`
}

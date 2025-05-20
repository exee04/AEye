-- Create quiz_results table
CREATE TABLE IF NOT EXISTS public.quiz_results (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    letter TEXT NOT NULL,
    is_correct BOOLEAN NOT NULL,
    response_time FLOAT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create user_stats table
CREATE TABLE IF NOT EXISTS public.user_stats (
    user_id TEXT PRIMARY KEY,
    total_attempts INTEGER DEFAULT 0,
    correct_answers INTEGER DEFAULT 0,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Set up Row Level Security (RLS)
ALTER TABLE public.quiz_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_stats ENABLE ROW LEVEL SECURITY;

-- Create policies for anonymous access
CREATE POLICY "Allow anonymous read access to quiz_results"
    ON public.quiz_results
    FOR SELECT
    TO anon
    USING (true);

CREATE POLICY "Allow anonymous insert to quiz_results"
    ON public.quiz_results
    FOR INSERT
    TO anon
    WITH CHECK (true);

CREATE POLICY "Allow anonymous read access to user_stats"
    ON public.user_stats
    FOR SELECT
    TO anon
    USING (true);

CREATE POLICY "Allow anonymous upsert to user_stats"
    ON public.user_stats
    FOR ALL
    TO anon
    USING (true)
    WITH CHECK (true); 
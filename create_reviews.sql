CREATE TABLE reviews (
    book_id INTEGER REFERENCES books,
    user_id INTEGER NOT NULL,
    score INTEGER NOT NULL,
    review VARCHAR NOT NULL
);


CREATE TABLE "users" (
  "id" uuid PRIMARY KEY,
  "personal_identificator" text NOT NULL,
  "name" text NOT NULL,
  "surname" text NOT NULL,
  "email" text NOT NULL,
  "birth_date" date NOT NULL,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL
);

CREATE TABLE "cards" (
  "id" uuid PRIMARY KEY NOT NULL,
  "user_id" uuid NOT NULL,
  "magstripe" text NOT NULL,
  "status" text NOT NULL,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL
);

CREATE TABLE "publications" (
  "id" uuid PRIMARY KEY NOT NULL,
  "title" text NOT NULL,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL
);

CREATE TABLE "publication_instances" (
  "id" uuid PRIMARY KEY NOT NULL,
  "publication_id" uuid NOT NULL,
  "publisher" text NOT NULL,
  "type" text NOT NULL,
  "status" text NOT NULL,
  "year" integer NOT NULL,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL
);

CREATE TABLE "authors" (
  "id" uuid PRIMARY KEY NOT NULL,
  "name" text NOT NULL,
  "surname" text NOT NULL,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL
);

CREATE TABLE "categories" (
  "id" uuid PRIMARY KEY NOT NULL,
  "name" text NOT NULL,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL
);

CREATE TABLE "publication_loans" (
  "id" uuid PRIMARY KEY NOT NULL,
  "user_id" uuid NOT NULL,
  "publication_instance_id" uuid NOT NULL,
  "start_date" timestamptz NOT NULL,
  "end_date" timestamptz NOT NULL,
  "duration" integer NOT NULL,
  "status" text NOT NULL
);

CREATE TABLE "reservations" (
  "id" uuid PRIMARY KEY NOT NULL,
  "publication_id" uuid NOT NULL,
  "user_id" uuid NOT NULL,
  "created_at" timestamptz NOT NULL
);

CREATE TABLE "publication_authors" (
  "publication_id" uuid NOT NULL,
  "author_id" uuid NOT NULL
);

CREATE TABLE "publication_categories" (
  "category_id" uuid NOT NULL,
  "publication_id" uuid NOT NULL
);

ALTER TABLE "publication_loans" ADD FOREIGN KEY ("publication_instance_id") REFERENCES "publication_instances" ("id") ON DELETE CASCADE;

ALTER TABLE "cards" ADD FOREIGN KEY ("user_id") REFERENCES "users" ("id");

ALTER TABLE "publication_instances" ADD FOREIGN KEY ("publication_id") REFERENCES "publications" ("id") ON DELETE CASCADE;

ALTER TABLE "reservations" ADD FOREIGN KEY ("publication_id") REFERENCES "publications" ("id") ON DELETE CASCADE;

ALTER TABLE "reservations" ADD FOREIGN KEY ("user_id") REFERENCES "users" ("id");

ALTER TABLE "publication_loans" ADD FOREIGN KEY ("user_id") REFERENCES "users" ("id");

ALTER TABLE "publication_categories" ADD FOREIGN KEY ("category_id") REFERENCES "categories" ("id") ON DELETE CASCADE;

ALTER TABLE "publication_categories" ADD FOREIGN KEY ("publication_id") REFERENCES "publications" ("id") ON DELETE CASCADE;

ALTER TABLE "publication_authors" ADD FOREIGN KEY ("publication_id") REFERENCES "publications" ("id") ON DELETE CASCADE;

ALTER TABLE "publication_authors" ADD FOREIGN KEY ("author_id") REFERENCES "authors" ("id") ON DELETE CASCADE;

ALTER TABLE users
ADD CONSTRAINT personal_identificator_unq
UNIQUE (
	personal_identificator
);

ALTER TABLE users
ADD CONSTRAINT email_unq
UNIQUE (
	email
);

ALTER TABLE cards ALTER COLUMN status SET DEFAULT 'inactive';

ALTER TABLE cards
ADD CONSTRAINT status_values
CHECK (
	status='active'
	OR status='inactive'
	OR status='expired'
);

ALTER TABLE publication_instances
ADD CONSTRAINT status_values
CHECK (
	status='available'
	OR status='reserved'
);

ALTER TABLE publication_instances
ADD CONSTRAINT type_values
CHECK (
	type='physical'
	OR type='ebook'
	OR type='audiobook'
);

ALTER TABLE publication_instances ALTER COLUMN status SET DEFAULT 'available';

ALTER TABLE categories
ADD CONSTRAINT category_name_unq
UNIQUE (
	name
);

ALTER TABLE publication_loans
ADD CONSTRAINT status_values
CHECK (
	status='active'
	OR status='returned'
	OR status='overdue'
);

ALTER TABLE publication_loans
ADD CONSTRAINT duration_minimal_value
CHECK (
	duration <= 14
	AND duration > 0
);

ALTER TABLE publication_loans ALTER COLUMN status SET DEFAULT 'active';

ALTER TABLE publication_authors 
ALTER COLUMN author_id
SET NOT NULL;

ALTER TABLE publication_categories
ALTER COLUMN category_id
SET NOT NULL;



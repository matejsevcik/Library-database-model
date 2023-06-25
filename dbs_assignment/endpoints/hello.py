from uuid import UUID, uuid4
from datetime import date, datetime
import psycopg2
import re
from fastapi import HTTPException
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, UUID4

from dbs_assignment.config import settings

from fastapi import FastAPI, APIRouter
from typing import Dict, Any, Optional

app = FastAPI()

router = APIRouter()


def check(email):
    regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
    email = str(email)
    if re.fullmatch(regex, email):
        return True

    else:
        return False


def table_exists(table_name: str, cur):
    cur.execute("""
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_name = %s
        )
    """, (table_name,))
    return cur.fetchone()


def create_database():
    connection = psycopg2.connect(host=settings.DATABASE_HOST, dbname=settings.DATABASE_NAME,
                                  user=settings.DATABASE_USER,
                                  password=settings.DATABASE_PASSWORD, port=settings.DATABASE_PORT)
    cur = connection.cursor(cursor_factory=RealDictCursor)

    check = table_exists('users', cur)['exists']
    if check:
        cur.close()
        connection.close()
        return

    fd = open('create_db.sql', 'r')
    sql_file = fd.read()
    fd.close()
    cur.execute(sql_file)
    connection.commit()

    cur.close()
    connection.close()


create_database()


# region Classes


class User(BaseModel):
    id: UUID | None = uuid4()
    personal_identificator: Optional[str] = None
    name: Optional[str] = None
    surname: Optional[str] = None
    email: Optional[str] = None
    birth_date: Optional[str] = None


class Card(BaseModel):
    id: UUID | None = uuid4()
    user_id: Optional[UUID] = None
    magstripe: Optional[str] = None
    status: Optional[str] = 'inactive'


class AuthorName(BaseModel):
    name: str
    surname: str


class Publication(BaseModel):
    id: UUID | None = uuid4()
    title: Optional[str] = None
    authors: Optional[list[AuthorName]]
    categories: Optional[list[str]]


class Instance(BaseModel):
    id: UUID | None = uuid4()
    publication_id: UUID
    publisher: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = 'available'
    year: Optional[int] = None


class Category(BaseModel):
    id: UUID | None = uuid4()
    name: Optional[str] = None


class Author(BaseModel):
    id: UUID | None = uuid4()
    name: Optional[str] = None
    surname: Optional[str] = None


class Rental(BaseModel):
    id: UUID | None = uuid4()
    user_id: Optional[UUID] = None
    publication_id: Optional[UUID] = None
    duration: Optional[int] = None


class Reservation(BaseModel):
    id: UUID | None = uuid4()
    user_id: Optional[UUID] = None
    publication_id: Optional[UUID] = None


# endregion

# region user

@router.get("/users/{userID}", status_code=200)
async def users_get(userID: UUID):
    connection = psycopg2.connect(host=settings.DATABASE_HOST, dbname=settings.DATABASE_NAME,
                                  user=settings.DATABASE_USER,
                                  password=settings.DATABASE_PASSWORD, port=settings.DATABASE_PORT)
    cur = connection.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
                WITH sel_user AS (SELECT * FROM users WHERE id=(%(userID)s)),
                reservations AS (SELECT JSON_AGG(JSON_BUILD_OBJECT('id', reservations.id, 'user_id', reservations.user_id, 'publication_id',
                                           reservations.publication_id)) AS reservations
                FROM reservations WHERE reservations.user_id = (%(userID)s)),
                rentals AS (SELECT JSON_AGG(JSON_BUILD_OBJECT('id', publication_loans.id, 'user_id', publication_loans.user_id,
                          'publication_instance_id', publication_loans.publication_instance_id,
                          'duration', publication_loans.duration,
                        'status', publication_loans.status)) AS rentals
                FROM publication_loans WHERE publication_loans.user_id = (%(userID)s))
                SELECT * FROM sel_user, reservations, rentals
                """,
                {'userID': str(userID)})

    result = cur.fetchone()

    if result is None:
        raise HTTPException(status_code=404, detail="User Not Found")

    cur.close()
    connection.close()

    if result['rentals'] is None:
        del result['rentals']
    if result['reservations'] is None:
        del result['reservations']

    return result


@router.patch("/users/{userID}", status_code=200)
async def users_patch(userID: UUID, update_values: Dict[str, Any]):
    connection = psycopg2.connect(host=settings.DATABASE_HOST, dbname=settings.DATABASE_NAME,
                                  user=settings.DATABASE_USER,
                                  password=settings.DATABASE_PASSWORD, port=settings.DATABASE_PORT)
    cur = connection.cursor(cursor_factory=RealDictCursor)

    if isinstance(update_values, dict):
        try:
            for val in update_values:
                cur.execute("""
                            UPDATE users
                            SET {} = (%(arg)s)
                            WHERE id = (%(userID)s)
                            """.format(val), {'arg': update_values[val], 'userID': str(userID)})
        except psycopg2.errors.UniqueViolation:
            raise HTTPException(status_code=409, detail="Email Already Taken")

        cur.execute("""
        UPDATE users
        set updated_at=now()
        WHERE id=(%(userID)s)
        RETURNING *
        """, {"userID": str(userID)})

    else:
        raise HTTPException(status_code=400, detail="Bad Request")

    connection.commit()
    result = cur.fetchone()

    cur.close()
    connection.close()

    if result is None:
        raise HTTPException(status_code=404, detail="User Not Found")
    return result


@router.post("/users", status_code=201)
async def users_post(user: User):
    connection = psycopg2.connect(host=settings.DATABASE_HOST, dbname=settings.DATABASE_NAME,
                                  user=settings.DATABASE_USER,
                                  password=settings.DATABASE_PASSWORD, port=settings.DATABASE_PORT)
    cur = connection.cursor(cursor_factory=RealDictCursor)

    if not check(user.email):
        raise HTTPException(status_code=400, detail="Missing Required Information")

    try:
        birth_date = datetime.strptime(user.birth_date, '%Y-%m-%d').date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format for birth_date field")

    try:
        cur.execute("""
                    INSERT INTO users
                    VALUES((%(id)s), (%(personal_identificator)s), (%(name)s), (%(surname)s),
                    (%(email)s), (%(birth_date)s), now(), now())
                    RETURNING *
                    """,
                    {'id': str(user.id),
                     'personal_identificator': user.personal_identificator,
                     'name': user.name,
                     'surname': user.surname,
                     'email': user.email,
                     'birth_date': user.birth_date})
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Email Already Taken")
    except psycopg2.errors.NotNullViolation:
        raise HTTPException(status_code=400, detail="Missing Required Information")

    connection.commit()
    result = cur.fetchone()

    cur.close()
    connection.close()

    return result


# endregion

# region cards


@router.get("/cards/{cardID}", status_code=200)
async def cards_get(cardID: UUID):
    connection = psycopg2.connect(host=settings.DATABASE_HOST, dbname=settings.DATABASE_NAME,
                                  user=settings.DATABASE_USER,
                                  password=settings.DATABASE_PASSWORD, port=settings.DATABASE_PORT)
    cur = connection.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
            SELECT *
            FROM cards
            WHERE cards.id=(%(cardID)s)
            """,
                {'cardID': str(cardID)})

    result = cur.fetchone()

    cur.close()
    connection.close()

    if result is None:
        raise HTTPException(status_code=404, detail="User Not Found")

    return result


@router.patch("/cards/{cardID}", status_code=200)
async def cards_patch(cardID: UUID, update_values: Dict[str, Any]):
    connection = psycopg2.connect(host=settings.DATABASE_HOST, dbname=settings.DATABASE_NAME,
                                  user=settings.DATABASE_USER,
                                  password=settings.DATABASE_PASSWORD, port=settings.DATABASE_PORT)
    cur = connection.cursor(cursor_factory=RealDictCursor)

    try:
        if isinstance(update_values, dict):
            for val in update_values:
                cur.execute("""
                            UPDATE cards
                            SET {} = %(arg2)s
                            WHERE cards.id = %(cardID)s
                            """.format(val), {'arg2': update_values[val], 'cardID': str(cardID)})

        cur.execute("""
            UPDATE cards
            set updated_at=now()
            WHERE id=(%(cardID)s)
            RETURNING *
            """, {"cardID": str(cardID)})

    except psycopg2.errors.CheckViolation:
        raise HTTPException(status_code=400, detail="Bad Request")

    connection.commit()
    result = cur.fetchone()

    cur.close()
    connection.close()

    if result is None:
        raise HTTPException(status_code=404, detail="User Not Found")

    return result


@router.post("/cards", status_code=201)
async def cards_post(card: Card):
    connection = psycopg2.connect(host=settings.DATABASE_HOST, dbname=settings.DATABASE_NAME,
                                  user=settings.DATABASE_USER,
                                  password=settings.DATABASE_PASSWORD, port=settings.DATABASE_PORT)
    cur = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cur.execute("""
                    INSERT INTO cards
                    VALUES((%(id)s), (%(user_id)s), (%(magstripe)s), (%(status)s), now(), now())
                    RETURNING *
                    """,
                    {'id': str(card.id),
                     'user_id': str(card.user_id),
                     'magstripe': card.magstripe,
                     'status': card.status})
    except psycopg2.errors.NotNullViolation:
        raise HTTPException(status_code=400, detail="Missing Required Information")

    connection.commit()
    result = cur.fetchone()

    cur.close()
    connection.close()

    return result


@router.delete("/cards/{cardID}", status_code=204)
async def cards_delete(cardID: UUID):
    connection = psycopg2.connect(host=settings.DATABASE_HOST, dbname=settings.DATABASE_NAME,
                                  user=settings.DATABASE_USER,
                                  password=settings.DATABASE_PASSWORD, port=settings.DATABASE_PORT)
    cur = connection.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
                DELETE FROM cards WHERE cards.id = (%(cardID)s)
                RETURNING *
                """,
                {'cardID': str(cardID)})

    result = cur.fetchone()
    if result is None:
        raise HTTPException(status_code=404, detail="Not Found")

    connection.commit()

    cur.close()
    connection.close()


# endregion

# region publications
@router.get("/publications/{publicationId}", status_code=200)
async def publications_get(publicationId: UUID):
    connection = psycopg2.connect(host=settings.DATABASE_HOST, dbname=settings.DATABASE_NAME,
                                  user=settings.DATABASE_USER,
                                  password=settings.DATABASE_PASSWORD, port=settings.DATABASE_PORT)
    cur = connection.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
                WITH pub AS (SELECT * FROM publications WHERE publications.id = (%(publicationId)s)),
                auth AS (SELECT JSON_AGG(JSON_BUILD_OBJECT('name', authors.name, 'surname', authors.surname)) AS authors
                FROM authors
                JOIN publication_authors ON publication_authors.author_id = authors.id
                WHERE publication_authors.publication_id = (%(publicationId)s)),
                cat AS (SELECT ARRAY_AGG(categories.name) AS categories
                FROM categories
                JOIN publication_categories ON publication_categories.category_id = categories.id
                WHERE publication_categories.publication_id = (%(publicationId)s))
                SELECT * FROM pub, auth, cat
                """,
                {'publicationId': str(publicationId)})

    result = cur.fetchone()

    cur.close()
    connection.close()

    if result is None:
        raise HTTPException(status_code=404, detail="User Not Found")

    return result


@router.post("/publications", status_code=201)
async def publications_post(publication: Publication):
    connection = psycopg2.connect(host=settings.DATABASE_HOST, dbname=settings.DATABASE_NAME,
                                  user=settings.DATABASE_USER,
                                  password=settings.DATABASE_PASSWORD, port=settings.DATABASE_PORT)
    cur = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cur.execute("""
                    INSERT INTO publications
                    VALUES((%(id)s), (%(title)s), now(), now())
                    RETURNING *
                    """,
                    {'id': str(publication.id),
                     'title': publication.title})

        result = cur.fetchone()
        result['authors'] = publication.authors
        result['categories'] = publication.categories

        if publication.authors is not None:
            if publication.authors[0].name is not None:
                for author in publication.authors:
                    cur.execute("""
                                INSERT INTO publication_authors
                                VALUES((%(publication_id)s),
                                (SELECT authors.id
                                FROM authors
                                WHERE authors.name=(%(author_name)s)
                                AND authors.surname=(%(author_surname)s)))
                                """,
                                {'publication_id': str(publication.id),
                                 'author_name': author.name,
                                 'author_surname': author.surname})

        if publication.categories is not None:
            for category in publication.categories:
                cur.execute("""
                            INSERT INTO publication_categories
                            VALUES(
                            (SELECT categories.id
                            FROM categories
                            WHERE categories.name=(%(category_name)s)),
                            (%(publication_id)s))
                            """,
                            {'publication_id': str(publication.id),
                             'category_name': category})

    except psycopg2.errors.NotNullViolation:
        raise HTTPException(status_code=400, detail="Something is wrong")

    connection.commit()

    cur.close()
    connection.close()

    return result


@router.delete("/publications/{publicationId}", status_code=204)
async def publications_delete(publicationId: UUID):
    connection = psycopg2.connect(host=settings.DATABASE_HOST, dbname=settings.DATABASE_NAME,
                                  user=settings.DATABASE_USER,
                                  password=settings.DATABASE_PASSWORD, port=settings.DATABASE_PORT)
    cur = connection.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
                DELETE FROM publications WHERE publications.id = (%(publicationId)s)
                RETURNING *
                """,
                {'publicationId': str(publicationId)})

    result = cur.fetchone()
    if result is None:
        raise HTTPException(status_code=404, detail="Not Found")

    connection.commit()

    cur.close()
    connection.close()


# endregion

# region instances
@router.post("/instances", status_code=201)
async def instances_post(instance: Instance):
    connection = psycopg2.connect(host=settings.DATABASE_HOST, dbname=settings.DATABASE_NAME,
                                  user=settings.DATABASE_USER,
                                  password=settings.DATABASE_PASSWORD, port=settings.DATABASE_PORT)
    cur = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cur.execute("""
                    INSERT INTO publication_instances
                    VALUES((%(id)s), (%(publication_id)s), (%(publisher)s), (%(type)s), (%(status)s),
                    (%(year)s), now(), now())
                    RETURNING *
                    """,
                    {'id': str(instance.id),
                     'publication_id': str(instance.publication_id),
                     'publisher': instance.publisher,
                     'type': instance.type,
                     'status': instance.status,
                     'year': instance.year})

    except psycopg2.errors.NotNullViolation:
        raise HTTPException(status_code=400, detail="Missing Required Information")

    connection.commit()
    result = cur.fetchone()

    cur.close()
    connection.close()

    if result is None:
        raise HTTPException(status_code=404, detail="User Not Found")

    return result


@router.get("/instances/{instanceId}", status_code=200)
async def instances_get(instanceId: UUID):
    connection = psycopg2.connect(host=settings.DATABASE_HOST, dbname=settings.DATABASE_NAME,
                                  user=settings.DATABASE_USER,
                                  password=settings.DATABASE_PASSWORD, port=settings.DATABASE_PORT)
    cur = connection.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
            SELECT *
            FROM publication_instances
            WHERE publication_instances.id=(%(instanceId)s)
            """,
                {'instanceId': str(instanceId)})

    result = cur.fetchone()

    cur.close()
    connection.close()

    if result is None:
        raise HTTPException(status_code=404, detail="User Not Found")

    return result


@router.delete("/instances/{instanceId}", status_code=204)
async def instances_delete(instanceId: UUID):
    connection = psycopg2.connect(host=settings.DATABASE_HOST, dbname=settings.DATABASE_NAME,
                                  user=settings.DATABASE_USER,
                                  password=settings.DATABASE_PASSWORD, port=settings.DATABASE_PORT)
    cur = connection.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
                DELETE FROM publication_instances WHERE publication_instances.id = (%(instanceId)s)
                RETURNING *
                """,
                {'instanceId': str(instanceId)})

    result = cur.fetchone()
    if result is None:
        raise HTTPException(status_code=404, detail="Not Found")

    connection.commit()

    cur.close()
    connection.close()


@router.patch("/instances/{instanceId}", status_code=200)
async def instances_patch(instanceId: UUID, update_values: Dict[str, Any]):
    connection = psycopg2.connect(host=settings.DATABASE_HOST, dbname=settings.DATABASE_NAME,
                                  user=settings.DATABASE_USER,
                                  password=settings.DATABASE_PASSWORD, port=settings.DATABASE_PORT)
    cur = connection.cursor(cursor_factory=RealDictCursor)

    if type(update_values) == 'dict':
        for val in update_values:
            cur.execute("""
                        UPDATE publication_instances
                        SET {} = (%(arg)s)
                        WHERE id = (%(instanceId)s)
                        """.format(val), {'arg': update_values[val], 'instanceId': str(instanceId)})

    cur.execute("""
    UPDATE publication_instances
    set updated_at=now()
    WHERE id=(%(instanceId)s)
    RETURNING *
    """, {"instanceId": str(instanceId)})

    connection.commit()
    result = cur.fetchone()

    cur.close()
    connection.close()

    if result is None:
        raise HTTPException(status_code=404, detail="User Not Found")

    return result


# endregion

# region authors
@router.post("/authors", status_code=201)
async def authors_post(author: Author):
    connection = psycopg2.connect(host=settings.DATABASE_HOST, dbname=settings.DATABASE_NAME,
                                  user=settings.DATABASE_USER,
                                  password=settings.DATABASE_PASSWORD, port=settings.DATABASE_PORT)
    cur = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cur.execute("""
                    INSERT INTO authors
                    VALUES((%(id)s), (%(name)s), (%(surname)s), now(), now())
                    RETURNING *
                    """,
                    {'id': str(author.id),
                     'name': author.name,
                     'surname': author.surname})
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Conflict")
    except psycopg2.errors.NotNullViolation:
        raise HTTPException(status_code=400, detail="Missing Required Information")

    connection.commit()
    result = cur.fetchone()

    cur.close()
    connection.close()

    return result


@router.get("/authors/{authorId}", status_code=200)
async def authors_get(authorId: UUID):
    connection = psycopg2.connect(host=settings.DATABASE_HOST, dbname=settings.DATABASE_NAME,
                                  user=settings.DATABASE_USER,
                                  password=settings.DATABASE_PASSWORD, port=settings.DATABASE_PORT)
    cur = connection.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
            SELECT *
            FROM authors
            WHERE authors.id=(%(authorId)s)
            """,
                {'authorId': str(authorId)})

    result = cur.fetchone()

    cur.close()
    connection.close()

    if result is None:
        raise HTTPException(status_code=404, detail="User Not Found")

    return result


@router.delete("/authors/{authorId}", status_code=204)
async def authors_delete(authorId: UUID):
    connection = psycopg2.connect(host=settings.DATABASE_HOST, dbname=settings.DATABASE_NAME,
                                  user=settings.DATABASE_USER,
                                  password=settings.DATABASE_PASSWORD, port=settings.DATABASE_PORT)
    cur = connection.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
                DELETE FROM authors WHERE authors.id = (%(authorId)s)
                RETURNING *
                """,
                {'authorId': str(authorId)})

    result = cur.fetchone()
    if result is None:
        raise HTTPException(status_code=404, detail="Not Found")

    connection.commit()

    cur.close()
    connection.close()


@router.patch("/authors/{authorId}", status_code=200)
async def authors_patch(authorId: UUID, update_values: Dict[str, Any]):
    connection = psycopg2.connect(host=settings.DATABASE_HOST, dbname=settings.DATABASE_NAME,
                                  user=settings.DATABASE_USER,
                                  password=settings.DATABASE_PASSWORD, port=settings.DATABASE_PORT)
    cur = connection.cursor(cursor_factory=RealDictCursor)

    if isinstance(update_values, dict):
        for val in update_values:
            cur.execute("""
                        UPDATE authors
                        SET {} = (%(arg)s)
                        WHERE id = (%(authorId)s)
                        """.format(val), {'arg': update_values[val], 'authorId': str(authorId)})

    cur.execute("""
    UPDATE authors
    set updated_at=now()
    WHERE id=(%(authorId)s)
    RETURNING *
    """, {"authorId": str(authorId)})

    connection.commit()
    result = cur.fetchone()

    cur.close()
    connection.close()

    if result is None:
        raise HTTPException(status_code=404, detail="User Not Found")

    return result


# endregion

# region categories
@router.post("/categories", status_code=201)
async def categories_post(category: Category):
    connection = psycopg2.connect(host=settings.DATABASE_HOST, dbname=settings.DATABASE_NAME,
                                  user=settings.DATABASE_USER,
                                  password=settings.DATABASE_PASSWORD, port=settings.DATABASE_PORT)
    cur = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cur.execute("""
                    INSERT INTO categories
                    VALUES((%(id)s), (%(name)s), now(), now())
                    RETURNING *
                    """,
                    {'id': str(category.id),
                     'name': category.name})
    except psycopg2.errors.NotNullViolation:
        raise HTTPException(status_code=400, detail="Missing Required Information")

    connection.commit()
    result = cur.fetchone()

    cur.close()
    connection.close()

    if result is None:
        raise HTTPException(status_code=404, detail="User Not Found")

    return result


@router.get("/categories/{categoryId}", status_code=200)
async def categories_get(categoryId: UUID):
    connection = psycopg2.connect(host=settings.DATABASE_HOST, dbname=settings.DATABASE_NAME,
                                  user=settings.DATABASE_USER,
                                  password=settings.DATABASE_PASSWORD, port=settings.DATABASE_PORT)
    cur = connection.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
            SELECT *
            FROM categories
            WHERE categories.id=(%(categoryId)s)
            """,
                {'categoryId': str(categoryId)})

    result = cur.fetchone()

    cur.close()
    connection.close()

    if result is None:
        raise HTTPException(status_code=404, detail="User Not Found")

    return result


@router.delete("/categories/{categoryId}", status_code=204)
async def categories_delete(categoryId: UUID):
    connection = psycopg2.connect(host=settings.DATABASE_HOST, dbname=settings.DATABASE_NAME,
                                  user=settings.DATABASE_USER,
                                  password=settings.DATABASE_PASSWORD, port=settings.DATABASE_PORT)
    cur = connection.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
                DELETE FROM categories WHERE categories.id = (%(categoryId)s)
                RETURNING *
                """,
                {'categoryId': str(categoryId)})
    result = cur.fetchone()
    if result is None:
        raise HTTPException(status_code=404, detail="Not Found")

    connection.commit()

    cur.close()
    connection.close()


@router.patch("/categories/{categoryId}", status_code=200)
async def categories_patch(categoryId: UUID, update_values: Dict[str, Any]):
    connection = psycopg2.connect(host=settings.DATABASE_HOST, dbname=settings.DATABASE_NAME,
                                  user=settings.DATABASE_USER,
                                  password=settings.DATABASE_PASSWORD, port=settings.DATABASE_PORT)
    cur = connection.cursor(cursor_factory=RealDictCursor)

    if isinstance(update_values, dict):
        for val in update_values:
            if not isinstance(val, str):
                raise HTTPException(status_code=400, detail="Bad Request")
            cur.execute("""
                        UPDATE categories
                        SET {} = (%(arg)s)
                        WHERE id = (%(categoryId)s)
                        """.format(val), {'arg': update_values[val], 'categoryId': str(categoryId)})

    cur.execute("""
    UPDATE categories
    set updated_at=now()
    WHERE id=(%(categoryId)s)
    RETURNING *
    """, {"categoryId": str(categoryId)})

    connection.commit()
    result = cur.fetchone()

    cur.close()
    connection.close()

    if result is None:
        raise HTTPException(status_code=404, detail="Category Not Found")

    return result


# endregion

# region rentals
@router.post("/rentals", status_code=201)
async def rentals_post(rental: Rental):
    connection = psycopg2.connect(host=settings.DATABASE_HOST, dbname=settings.DATABASE_NAME,
                                  user=settings.DATABASE_USER,
                                  password=settings.DATABASE_PASSWORD, port=settings.DATABASE_PORT)
    cur = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cur.execute("""
            select id from publication_instances
            where publication_id=(%(publication_id)s)
            and status='available'
            limit 1
            """, {'publication_id': str(rental.publication_id)})

        result = cur.fetchone()
        if result:
            publication_instance_id = result['id']  # Access the first element of the result tuple
            print(publication_instance_id)
        else:
            raise HTTPException(status_code=400, detail="Bad request")

        cur.execute("""
                    INSERT INTO publication_loans
                    VALUES((%(id)s), (%(user_id)s), (%(publication_id)s), now(),
                    now() + INTERVAL '(%(duration)s) D', (%(duration)s))
                    RETURNING *
                    """,
                    {'id': str(rental.id),
                     'user_id': str(rental.user_id),
                     'publication_id': str(publication_instance_id),
                     'duration': rental.duration})

        result = cur.fetchone()

        cur.execute("""
        UPDATE publication_instances
        SET updated_at=now(),
        status='reserved'
        WHERE publication_instances.id=(%(publication_instance_id)s)
        AND publication_instances.type='physical'
        """, {'publication_instance_id': str(publication_instance_id)})

    except psycopg2.errors.NotNullViolation:
        raise HTTPException(status_code=400, detail="Missing Required Information")

    connection.commit()

    cur.close()
    connection.close()

    return result


@router.get("/rentals/{rentalId}", status_code=200)
async def rentals_get(rentalId: UUID):
    connection = psycopg2.connect(host=settings.DATABASE_HOST, dbname=settings.DATABASE_NAME,
                                  user=settings.DATABASE_USER,
                                  password=settings.DATABASE_PASSWORD, port=settings.DATABASE_PORT)
    cur = connection.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
            SELECT duration, id, publication_instance_id, status, user_id
            FROM publication_loans
            WHERE publication_loans.id=(%(rentalId)s)
            """,
                {'rentalId': str(rentalId)})

    result = cur.fetchone()

    cur.close()
    connection.close()

    if result is None:
        raise HTTPException(status_code=404, detail="Not Found")

    return result


# endregion

# region reservations
@router.post("/reservations", status_code=201)
async def reservations_post(reservation: Reservation):
    connection = psycopg2.connect(host=settings.DATABASE_HOST, dbname=settings.DATABASE_NAME,
                                  user=settings.DATABASE_USER,
                                  password=settings.DATABASE_PASSWORD, port=settings.DATABASE_PORT)
    cur = connection.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
                    INSERT INTO reservations
                    VALUES((%(id)s), (%(publication_id)s), (%(user_id)s), now())
                    RETURNING *
                    """,
                    {'id': str(reservation.id),
                     'user_id': str(reservation.user_id),
                     'publication_id': str(reservation.publication_id)})

    except psycopg2.errors.NotNullViolation:
        raise HTTPException(status_code=400, detail="Missing Required Information")

    connection.commit()
    result = cur.fetchone()
    cur.close()
    connection.close()

    if result is None:
        raise HTTPException(status_code=404, detail="User Not Found")

    return result


@router.get("/reservations/{reservationId}", status_code=200)
async def reservations_get(reservationId: UUID):
    connection = psycopg2.connect(host=settings.DATABASE_HOST, dbname=settings.DATABASE_NAME,
                                  user=settings.DATABASE_USER,
                                  password=settings.DATABASE_PASSWORD, port=settings.DATABASE_PORT)
    cur = connection.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
            SELECT *
            FROM reservations
            WHERE reservations.id=(%(reservationId)s)
            """,
                {'reservationId': str(reservationId)})

    result = cur.fetchone()

    cur.close()
    connection.close()

    if result is None:
        raise HTTPException(status_code=404, detail="User Not Found")

    return result


@router.delete("/reservations/{reservationId}", status_code=204)
async def reservations_delete(reservationId: UUID):
    connection = psycopg2.connect(host=settings.DATABASE_HOST, dbname=settings.DATABASE_NAME,
                                  user=settings.DATABASE_USER,
                                  password=settings.DATABASE_PASSWORD, port=settings.DATABASE_PORT)
    cur = connection.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
                DELETE FROM reservations WHERE reservations.id = (%(reservationId)s)
                RETURNING *
                """,
                {'reservationId': str(reservationId)})

    result = cur.fetchone()
    if result is None:
        raise HTTPException(status_code=404, detail="Not Found")

    connection.commit()

    cur.close()
    connection.close()
# endregion

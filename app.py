# Flask 관련 기능들을 가져옴
from flask import Flask, render_template, request, redirect
# MySQL(MariaDB) 연결용 라이브러리
import pymysql
import os
from dotenv import load_dotenv

# .env 파일 내용을 환경변수로 불러옴
load_dotenv()

app = Flask(__name__)

# DB 연결 함수
def get_connection():
    return pymysql.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        db=os.getenv("DB_NAME"),
        charset="utf8mb4",
        # DictCursor를 쓰면 결과를 {"id":1, "title":"..."} 형태(딕셔너리)로 받을 수 있음
        # -> HTML에서 post.title 처럼 쓰기 편해짐
        cursorclass=pymysql.cursors.DictCursor
    )

# "/" 주소로 접속하면 게시글 목록을 보여줌 (검색 기능 포함)
@app.route("/")
def list_posts():
    # URL의 쿼리 파라미터(?search_type=...&keyword=...)를 가져옴
    # 값이 없으면 기본값 사용 (전체 목록 보여주기 위함)
    search_type = request.args.get("search_type", "all")
    keyword = request.args.get("keyword", "")

    conn = get_connection()
    cursor = conn.cursor()

    # 검색어가 없으면 -> 전체 글 목록 조회
    if keyword == "":
        cursor.execute("SELECT * FROM posts ORDER BY id DESC")

    # 검색어가 있으면 -> 검색 기준에 따라 다른 SQL 실행
    else:
        # LIKE %키워드% : 키워드가 포함된 데이터를 찾는 SQL 문법
        like_keyword = f"%{keyword}%"

        if search_type == "title":
            # 제목에서만 검색
            cursor.execute(
                "SELECT * FROM posts WHERE title LIKE %s ORDER BY id DESC",
                (like_keyword,)
            )
        elif search_type == "content":
            # 내용에서만 검색
            cursor.execute(
                "SELECT * FROM posts WHERE content LIKE %s ORDER BY id DESC",
                (like_keyword,)
            )
        else:
            # 전체(제목 OR 내용)에서 검색
            cursor.execute(
                "SELECT * FROM posts WHERE title LIKE %s OR content LIKE %s ORDER BY id DESC",
                (like_keyword, like_keyword)
            )

    posts = cursor.fetchall()
    conn.close()

    # HTML에 posts뿐 아니라, 검색 상태(search_type, keyword)도 같이 넘겨줌
    # -> 검색 후에도 검색창에 입력했던 값이 유지되도록 하기 위함
    return render_template("list.html", posts=posts, search_type=search_type, keyword=keyword)

# "/write" 주소로 GET 요청이 오면 -> 글쓰기 폼 화면을 보여줌
# "/write" 주소로 POST 요청이 오면 -> 폼에서 보낸 데이터를 DB에 저장함
@app.route("/write", methods=["GET", "POST"])
def write_post():
    # GET 요청일 때: 그냥 글쓰기 화면만 보여줌
    if request.method == "GET":
        return render_template("write.html")

    # POST 요청일 때: 폼에서 입력한 값들을 받아옴
    title = request.form["title"]
    author = request.form["author"]
    content = request.form["content"]

    conn = get_connection()
    cursor = conn.cursor()

    # %s는 값이 들어갈 자리(placeholder). 값은 뒤에 튜플로 따로 넘겨줌
    # -> 이렇게 하면 SQL 인젝션 공격을 방지할 수 있음 (직접 문자열 합치기 X)
    cursor.execute(
        "INSERT INTO posts (title, author, content) VALUES (%s, %s, %s)",
        (title, author, content)
    )
    conn.commit()   # INSERT는 commit()을 해야 실제로 DB에 저장됨 (TCL)
    conn.close()

    # 저장 후 목록 페이지("/")로 이동시킴
    return redirect("/")

# "/post/1", "/post/2" 처럼 숫자가 붙은 주소로 접속하면 해당 글 상세보기를 보여줌
# <int:post_id> : URL의 숫자 부분을 post_id라는 변수로 받아옴
@app.route("/post/<int:post_id>")
def view_post(post_id):
    conn = get_connection()
    cursor = conn.cursor()

    # post_id에 해당하는 글 하나만 조회
    cursor.execute("SELECT * FROM posts WHERE id = %s", (post_id,))
    post = cursor.fetchone()   # 결과가 1개뿐이므로 fetchone() 사용

    conn.close()

    return render_template("detail.html", post=post)

# "/edit/1" 같은 주소로 GET 요청 -> 수정 폼(기존 내용 채워진) 보여줌
# "/edit/1" 같은 주소로 POST 요청 -> 수정된 내용을 DB에 반영
@app.route("/edit/<int:post_id>", methods=["GET", "POST"])
def edit_post(post_id):
    conn = get_connection()
    cursor = conn.cursor()

    if request.method == "GET":
        # 수정 폼에 기존 데이터를 채워넣기 위해 먼저 조회
        cursor.execute("SELECT * FROM posts WHERE id = %s", (post_id,))
        post = cursor.fetchone()
        conn.close()
        return render_template("edit.html", post=post)

    # POST 요청일 때: 수정 폼에서 보낸 새 값들을 받아옴
    title = request.form["title"]
    author = request.form["author"]
    content = request.form["content"]

    # UPDATE 문으로 해당 id의 글 내용을 새 값으로 덮어씀
    # updated_at 컬럼은 테이블 설계 시 ON UPDATE CURRENT_TIMESTAMP로 설정해둬서 자동 갱신됨
    cursor.execute(
        "UPDATE posts SET title=%s, author=%s, content=%s WHERE id=%s",
        (title, author, content, post_id)
    )
    conn.commit()
    conn.close()

    # 수정 완료 후 해당 글의 상세보기 페이지로 이동
    return redirect(f"/post/{post_id}")

# "/delete/1" 같은 주소로 POST 요청이 오면 해당 글을 삭제함
# 삭제는 되돌릴 수 없는 작업이라 GET이 아니라 POST로만 받도록 함
@app.route("/delete/<int:post_id>", methods=["POST"])
def delete_post(post_id):
    conn = get_connection()
    cursor = conn.cursor()

    # 해당 id의 글을 DB에서 완전히 삭제
    cursor.execute("DELETE FROM posts WHERE id = %s", (post_id,))
    conn.commit()
    conn.close()

    # 삭제 후 목록 페이지로 이동
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)
function shuffleManitto() {

    fetch("/api/shuffle", {
        method: "POST"
    })

    .then(response => response.json())

    .then(data => {

        if (data.result === "success") {

            alert("마니또 배정이 완료되었습니다!");

        } else {

            alert("마니또 배정에 실패했습니다.");
        }

    })

    .catch(error => {

        console.error(error);

        alert("마니또 배정 중 오류가 발생했습니다.");

    });
}

function showManitto() {
    loadCard(
        "/dashboard/showManitto",
        "내 마니또",
        false
    );
}


function showManitti() {
    loadCard(
        "/dashboard/showManitti",
        "내 마니띠",
        true
    );
}


function loadCard(url, title, showRating) {

    fetch(url)
        .then(response => response.json())

        .then(data => {

            if (data.result !== "success") {
                alert(data.message);
                return;
            }

            const card =
                document.getElementById("manitto-card");

            const targetUser = data.user;


            document.getElementById("card-title")
                .innerText = title;

            document.getElementById("card-name")
                .innerText = targetUser.name;

            document.getElementById("card-mbti")
                .innerText = targetUser.mbti;

            document.getElementById("card-want")
                .innerText = targetUser.want;


            const extra =
                document.getElementById("manitti-extra");

            if (showRating) {
                extra.style.display = "block";
            } else {
                extra.style.display = "none";
            }


            /* 이미 뒤집힌 상태여도
               다시 뒤집히는 애니메이션 */
            card.classList.remove("flipped");

            setTimeout(function () {
                card.classList.add("flipped");
            }, 50);

        })

        .catch(error => {
            console.error(error);

            alert(
                "사용자 정보를 불러오지 못했습니다."
            );
        });
}


/* =============================
   별점 등록
============================= */
function submitRating() {

    const selectedRating =
        document.querySelector(
            'input[name="rating"]:checked'
        );


    if (!selectedRating) {

        alert("별점을 선택해주세요.");

        return;
    }


    const rating =
        Number(selectedRating.value);


    /*
       app.py의 /api/likes는

       request.form.get("like")

       로 받고 있으므로 JSON이 아니라
       form 형식으로 전송
    */

    const body =
        new URLSearchParams();

    body.append("like", rating);


    fetch("/api/likes", {

        method: "POST",

        headers: {
            "Content-Type":
                "application/x-www-form-urlencoded"
        },

        body: body

    })

    .then(response => response.json())

    .then(data => {

        if (data.result === "success") {

            alert("별점이 등록되었습니다.");

            /*
               다시 dashboard를 불러오면
               DB에서 랭킹을 다시 계산함
            */
            location.reload();

        } else {

            alert(
                data.message ||
                "별점 등록에 실패했습니다."
            );
        }

    })

    .catch(error => {

        console.error(error);

        alert(
            "별점 등록 중 오류가 발생했습니다."
        );

    });
}


/* =============================
   이모티콘
============================= */

document.addEventListener("DOMContentLoaded", function () {

    const stars = document.querySelectorAll(".star");
    const ratingEmoji = document.getElementById("rating-emoji");
    const starRating = document.querySelector(".star-rating");


    // 별점에 따른 이모티콘
    function getEmoji(rating) {

        switch (rating) {

            case 1:
                return "😭";

            case 2:
                return "😢";

            case 3:
                return "🙂";

            case 4:
                return "😄";

            case 5:
                return "😍";

            default:
                return "🙂";
        }
    }


    // 각 별에 마우스를 올렸을 때
    stars.forEach(function (star) {

        star.addEventListener("mouseenter", function () {

            const rating = Number(this.dataset.rating);

            ratingEmoji.innerText = getEmoji(rating);

        });


        // 별을 클릭했을 때도 해당 표정 유지
        star.addEventListener("click", function () {

            const rating = Number(this.dataset.rating);

            ratingEmoji.innerText = getEmoji(rating);

        });

    });


    // 별 영역에서 마우스가 빠져나갔을 때
    starRating.addEventListener("mouseleave", function () {

        const selectedRating =
            document.querySelector(
                'input[name="rating"]:checked'
            );


        // 선택한 별점이 있으면 선택한 점수의 표정 유지
        if (selectedRating) {

            const rating =
                Number(selectedRating.value);

            ratingEmoji.innerText =
                getEmoji(rating);

        } else {

            // 아직 선택하지 않았다면 기본 표정
            ratingEmoji.innerText = "🙂";

        }

    });

});
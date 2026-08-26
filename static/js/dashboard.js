function showManitto() {
  loadCard("/dashboard/showManitto", "내 마니또", false);
}

function showManitti() {
  loadCard("/dashboard/showManitti", "내 마니띠", true);
}

function loadCard(url, title, showRating) {
  fetch(url)
    .then((response) => response.json())
    .then((data) => {
      if (data.result !== "success") {
        alert(data.message || "사용자 정보를 불러오지 못했습니다.");
        return;
      }

      const card = document.getElementById("manitto-card");
      const targetUser = data.user;

      document.getElementById("card-title").innerText = title;
      document.getElementById("card-name").innerText = targetUser.name;
      document.getElementById("card-mbti").innerText = targetUser.mbti;
      document.getElementById("card-want").innerText = targetUser.want;
      document.getElementById("manitti-extra").style.display = showRating
        ? "block"
        : "none";

      card.classList.remove("flipped");
      setTimeout(() => card.classList.add("flipped"), 50);
    })
    .catch((error) => {
      console.error(error);
      alert("사용자 정보를 불러오지 못했습니다.");
    });
}

function submitRating() {
  const selectedRating = document.querySelector('input[name="rating"]:checked');

  if (!selectedRating) {
    alert("별점을 선택해주세요.");
    return;
  }

  const body = new URLSearchParams();
  body.append("like", selectedRating.value);

  fetch("/api/likes", {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body,
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.result === "success") {
        alert("별점이 등록되었습니다.");
        location.reload();
        return;
      }

      alert(data.message || "별점 등록에 실패했습니다.");
    })
    .catch((error) => {
      console.error(error);
      alert("별점 등록 중 오류가 발생했습니다.");
    });
}

function handleShuffle() {
  fetch("/api/shuffle", { method: "POST" })
    .then((response) => response.json())
    .then((data) => {
      if (data.result === "success") {
        alert("마니또 배정이 완료되었습니다. 공개 상태는 비공개로 초기화되었습니다.");
        updateGameStatus(false);
        return;
      }

      alert(data.message || "마니또 배정에 실패했습니다.");
    })
    .catch((error) => {
      console.error(error);
      alert("마니또 배정 중 오류가 발생했습니다.");
    });
}

function handleToggleOpen() {
  fetch("/api/toggle-open", { method: "POST" })
    .then((response) => response.json())
    .then((data) => {
      if (data.result === "success") {
        updateGameStatus(data.is_open);
        alert(`마니또 상태가 ${data.is_open ? "공개" : "비공개"}로 전환되었습니다.`);
        return;
      }

      alert(data.message || "상태 전환에 실패했습니다.");
    })
    .catch((error) => {
      console.error(error);
      alert("상태 전환 중 오류가 발생했습니다.");
    });
}

function updateGameStatus(isOpen) {
  const status = document.getElementById("game-status");
  if (status) {
    status.innerText = `현재 상태: ${isOpen ? "공개" : "비공개"}`;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const stars = document.querySelectorAll(".star");
  const ratingEmoji = document.getElementById("rating-emoji");
  const starRating = document.querySelector(".star-rating");

  if (!ratingEmoji || !starRating) {
    return;
  }

  const getEmoji = (rating) => {
    const emojis = ["🙂", "😭", "😢", "🙂", "😄", "😍"];
    return emojis[rating] || emojis[0];
  };

  stars.forEach((star) => {
    const showStarEmoji = () => {
      ratingEmoji.innerText = getEmoji(Number(star.dataset.rating));
    };

    star.addEventListener("mouseenter", showStarEmoji);
    star.addEventListener("click", showStarEmoji);
  });

  starRating.addEventListener("mouseleave", () => {
    const selectedRating = document.querySelector(
      'input[name="rating"]:checked',
    );
    ratingEmoji.innerText = selectedRating
      ? getEmoji(Number(selectedRating.value))
      : getEmoji(0);
  });
});

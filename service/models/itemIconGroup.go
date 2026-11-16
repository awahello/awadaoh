package models

import (
	"gorm.io/gorm"
)

type ItemIconGroup struct {
	BaseModel
	Icon        string `json:"icon"`
	Title       string `gorm:"type:varchar(50)" json:"title"`
	Description string `gorm:"type:varchar(1000)" json:"description"`
	Sort        int    `gorm:"type:int(11)" json:"sort"`
	// 可见性：0 公开（谁都能看）；1 登录后可见（访客看不到）；2 隐藏（谁都不渲染，配置保留）
	Visible int  `gorm:"type:tinyint(1);default:0" json:"visible"`
	UserId  uint `json:"userId"`
	User    User `json:"user"`
}

const (
	GROUP_VISIBLE_PUBLIC = 0 // 公开
	GROUP_VISIBLE_LOGIN  = 1 // 登录后可见
	GROUP_VISIBLE_HIDDEN = 2 // 隐藏
)


func (m *ItemIconGroup) DeleteByUserId(db *gorm.DB, userId uint) (err error) {
	err = db.Delete(&ItemIconGroup{}, "user_id = ?", userId).Error
	return
}

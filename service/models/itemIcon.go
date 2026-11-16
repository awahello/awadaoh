package models

import (
	"awadaoh/models/datatype"

	"gorm.io/gorm"
)

type ItemIcon struct {
	BaseModel
	IconJson        string                    `gorm:"type:varchar(1000)" json:"-"`
	Icon            datatype.ItemIconIconInfo `gorm:"-" json:"icon"`
	Title           string                    `gorm:"type:varchar(50)" json:"title"`
	Url             string                    `gorm:"type:varchar(1000)" json:"url"`
	LanUrl          string                    `gorm:"type:varchar(1000)" json:"lanUrl"`
	Description     string                    `gorm:"type:varchar(1000)" json:"description"`
	OpenMethod      int                       `gorm:"type:tinyint(1)" json:"openMethod"`
	Sort            int                       `gorm:"type:int(11)" json:"sort"`
	// 点击次数：用来「按使用频率排序」。访客点一次 +1，不做去重 ——
	// 目的是「常用的排前面」，不是审计，所以简单计数就够。
	ClickCount      int                       `gorm:"type:int(11);default:0" json:"clickCount"`
	ItemIconGroupId int                       `json:"itemIconGroupId"`
	UserId          uint                      `json:"userId"`
	User            User                      `json:"user"`
	// 以下不落库，只在响应里告诉前端这张卡要不要打码 / 要不要提示内网
	Private       bool `gorm:"-" json:"private,omitempty"`
	Masked        bool `gorm:"-" json:"masked,omitempty"`
	NeedsIntranet bool `gorm:"-" json:"needsIntranet,omitempty"`
}

func (m *ItemIcon) DeleteByItemIconGroupIds(db *gorm.DB, userId uint, itemIconGroupIds []uint) (err error) {
	err = db.Delete(&ItemIcon{}, "item_icon_group_id in ? AND user_id=?", itemIconGroupIds, userId).Error
	return
}

func (m *ItemIcon) DeleteByUserId(db *gorm.DB, userId uint) (err error) {
	return db.Delete(&ItemIcon{}, "user_id=?", userId).Error
}

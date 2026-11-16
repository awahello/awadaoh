package database

import (
	"log"
	"os"
	"path"
	"strings"
	"awadaoh/lib/cmn"
	"awadaoh/models"
	"time"

	"gorm.io/driver/mysql"
	_ "gorm.io/driver/mysql"
	"gorm.io/driver/sqlite"
	_ "gorm.io/driver/sqlite"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
	"gorm.io/gorm/schema"
)

const (
	MYSQL  = "mysql"
	SQLITE = "sqlite"
)

// 出厂默认密码。创建管理员、重置密码、启动日志里那句「密码是不是出厂值」，
// 全都读这一处 —— 以前这三处各写一份字符串，改一处漏两处就是「默认密码不对」。
const DefaultAdminPassword = "12345678"

type DbClient interface {
	Connect() (db *gorm.DB, err error)
}

type MySQLConfig struct {
	Username    string
	Password    string
	Host        string
	Port        string
	Database    string
	WaitTimeout int
}

type SQLiteConfig struct {
	Filename string
}

func DbInit(dbClient DbClient) (db *gorm.DB, dbErr error) {
	db, dbErr = dbClient.Connect()
	if dbErr != nil {
		return
	}
	return
}

// Connect mysql连接
func (d *MySQLConfig) Connect() (db *gorm.DB, err error) {
	dsn := d.Username + ":" + d.Password + "@tcp(" + d.Host + ":" + d.Port + ")/" + d.Database + "?charset=utf8mb4&parseTime=True&loc=Local"
	db, err = gorm.Open(mysql.Open(dsn), &gorm.Config{
		Logger: GetLogger(),
		NamingStrategy: schema.NamingStrategy{
			// TablePrefix:   "blog_",
			SingularTable: true,
		},
		DisableForeignKeyConstraintWhenMigrating: true,
	})
	sqlDb, _ := db.DB()
	sqlDb.SetMaxIdleConns(10)  // SetMaxIdleConns 设置空闲连接池中连接的最大数量
	sqlDb.SetMaxOpenConns(100) // SetMaxOpenConns 设置打开数据库连接的最大数量。
	wait_timeout := d.WaitTimeout
	sqlDb.SetConnMaxLifetime(time.Duration(wait_timeout * int(time.Second))) // SetConnMaxLifetime 设置了连接可复用的最大时间。
	return
}

// Connect sqllite3连接
func (d *SQLiteConfig) Connect() (db *gorm.DB, err error) {
	filePath := d.Filename
	exists := false
	if exists, err = cmn.PathExists(path.Dir(filePath)); err != nil {
		return
	} else {

		// 创建文件夹
		if !exists {
			if err = os.MkdirAll(path.Dir(filePath), 0700); err != nil {
				return
			}
		}

		db, err = gorm.Open(sqlite.Open(filePath), &gorm.Config{
			Logger: GetLogger(),
			NamingStrategy: schema.NamingStrategy{
				SingularTable: true,
			},
		})
	}

	return
}

// 日志
func GetLogger() logger.Interface {
	return logger.New(
		log.New(os.Stdout, "\r\n", log.LstdFlags), // io writer（日志输出的目标，前缀和日志包含的内容——译者注）
		logger.Config{
			SlowThreshold:             time.Second, // 慢 SQL 阈值
			LogLevel:                  logger.Warn, // 日志级别
			IgnoreRecordNotFoundError: true,        // 忽略ErrRecordNotFound（记录未找到）错误
			Colorful:                  true,        // 彩色打印
		},
	)

}

// 创建数据库
func CreateDatabase(driver string, db *gorm.DB) error {

	// mysql特殊处理
	if driver == MYSQL {
		db = db.Set("gorm:table_options", "ENGINE=InnoDB")
	}

	// 创建数据表
	err := db.AutoMigrate(
		&models.User{},
		&models.SystemSetting{},
		&models.ItemIcon{},
		&models.UserConfig{},
		&models.File{},
		&models.ItemIconGroup{},
		&models.ModuleConfig{},
	)

	return err
}

// 初始化一个用户,一个用户都没有的时候创建一个
func NotFoundAndCreateUser(db *gorm.DB) error {
	fUser := models.User{}
	if err := db.First(&fUser).Error; err != nil {
		if err != gorm.ErrRecordNotFound {
			return err
		}
		// 默认管理员：用户名就是 admin，别再让人去猜 admin@sun.cc
		username := "admin"
		fUser.Mail = username
		fUser.Username = username
		fUser.Name = username
		fUser.Status = 1
		fUser.Role = 1
		fUser.Password = cmn.PasswordEncryption(DefaultAdminPassword)

		if errCreate := db.Create(&fUser).Error; errCreate != nil {
			return errCreate
		}
	}

	return nil
}

// 老库兼容：上游默认管理员用户名是 admin@sun.cc，我们改成了 admin。
// 已经在跑的实例库里还留着旧名字，用户照着文档敲 admin 只会得到
// 「账号或密码错误」，然后以为密码也不对（这就是「默认账号密码是错的」的由来）。
// 这里做一次幂等改名：只在「旧名字存在」且「新名字还没被占用」时动手。
func MigrateLegacyAdminUsername(db *gorm.DB) {
	const (
		legacy = "admin@sun.cc"
		fixed  = "admin"
	)

	var n int64
	if err := db.Model(&models.User{}).Where("username = ?", fixed).Count(&n).Error; err != nil || n > 0 {
		return
	}

	old := models.User{}
	if err := db.Where("username = ?", legacy).First(&old).Error; err != nil {
		return
	}

	if err := db.Model(&models.User{}).Where("id = ?", old.ID).
		Update("username", fixed).Error; err != nil {
		log.Println("老库管理员改名失败:", err)
		return
	}
	log.Printf("老库管理员用户名 %s -> %s（id=%d）", legacy, fixed, old.ID)
}

// ResetAdminPassword 把第一个管理员的密码打回出厂默认值，并清掉 token。
// 用 map 而不是 struct + Select：struct 更新时 GORM 会跳过零值字段，
// token 想置空还得额外 Select 一次，容易漏。map 没有这个坑。
func ResetAdminPassword(db *gorm.DB) (models.User, error) {
	var u models.User
	if err := db.Where("role = ?", 1).Order("id asc").First(&u).Error; err != nil {
		return u, err
	}
	err := db.Model(&models.User{}).Where("id = ?", u.ID).
		Updates(map[string]interface{}{
			"password": cmn.PasswordEncryption(DefaultAdminPassword),
			"token":    "",
		}).Error
	return u, err
}

// ResetAdminByEnv 给「进不去后台」留一条不用敲命令的出路。
//
// 用法：AWADAOH_RESET_ADMIN=1 重启容器，第一个管理员的密码就回到出厂默认值，
// 并把用户名密码打在日志里。对 NAS 用户来说，改一行 compose 比 docker exec 里
// 拼参数现实得多；而 -password-reset 那条路仍然留着。
func ResetAdminByEnv(db *gorm.DB) {
	v := strings.ToLower(strings.TrimSpace(os.Getenv("AWADAOH_RESET_ADMIN")))
	if v != "1" && v != "true" && v != "yes" && v != "on" {
		return
	}
	u, err := ResetAdminPassword(db)
	if err != nil {
		log.Println("AWADAOH_RESET_ADMIN 重置失败:", err)
		return
	}
	log.Println("=============== 管理员密码已重置 ===============")
	log.Printf("  用户名  %s", u.Username)
	log.Printf("  密  码  %s", DefaultAdminPassword)
	log.Println("  进去以后到「设置 → 账号」改掉它")
	log.Println("  !! 记得把 AWADAOH_RESET_ADMIN 从 compose 里删掉，")
	log.Println("     否则每次重启都会再重置一次")
	log.Println("==============================================")
}

// 启动时把管理员账号打出来。
// 为什么需要：上游默认用户名是 admin@sun.cc，我们改成了 admin；老库被上面那个函数
// 改名之后密码还是上游那一套，用户照文档敲默认密码只会得到「用户名或密码错误」，
// 而且根本不知道去哪儿看自己到底叫什么。打在启动日志里，一眼就能对上。
func LogAdminAccounts(db *gorm.DB) {
	var users []models.User
	if err := db.Where("role = ?", 1).Order("id asc").Limit(10).Find(&users).Error; err != nil || len(users) == 0 {
		return
	}

	def := cmn.PasswordEncryption(DefaultAdminPassword)
	for _, u := range users {
		// 这一句直接回答「我该敲什么密码」：出厂值就是出厂值，
		// 不是的话就别猜了，重置。
		state := "密码不是出厂默认值"
		if u.Password == def {
			state = "密码 = 出厂默认值"
		}
		log.Printf("管理员 id=%d 用户名=%s 状态=%d %s", u.ID, u.Username, u.Status, state)
	}
	log.Println("登录提示：用户名打上面的「用户名」，密码是出厂默认值或你自己改过的那个")
	log.Println("进不去就跑: docker exec -it <容器名> /app/awadaoh -password-reset")
	log.Println("           或设 AWADAOH_RESET_ADMIN=1 重启容器（会自动重置并打印账号密码）")
}

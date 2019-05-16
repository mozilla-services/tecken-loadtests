// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at http://mozilla.org/MPL/2.0/.

package main

import (
	"archive/zip"
	"bytes"
	"fmt"
	"io"
	"io/ioutil"
	"log"
	"math/rand"
	"os"
	"path/filepath"
	"strings"
	"time"

	// Remember to...  go get github.com/pyk/byten
	"github.com/pyk/byten"
)

func DumpAndExtract(dest string, buffer []byte, name string) {
	size := int64(len(buffer))
	zipReader, err := zip.NewReader(bytes.NewReader(buffer), size)
	if err != nil {
		log.Fatal(err)
	}
	for _, f := range zipReader.File {
		rc, err := f.Open()
		if err != nil {
			log.Fatal(err)
		}
		defer rc.Close()
		fpath := filepath.Join(dest, f.Name)
		if f.FileInfo().IsDir() {
			os.MkdirAll(fpath, os.ModePerm)
		} else {
			// Make File
			var fdir string
			if lastIndex := strings.LastIndex(fpath, string(os.PathSeparator)); lastIndex > -1 {
				fdir = fpath[:lastIndex]
			}
			err = os.MkdirAll(fdir, os.ModePerm)
			if err != nil {
				log.Fatal(err)
			}
			f, err := os.OpenFile(
				fpath, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, f.Mode())
			if err != nil {
				log.Fatal(err)
			}
			defer f.Close()

			_, err = io.Copy(f, rc)
			if err != nil {
				log.Fatal(err)
			}
		}
	}
}

func Shuffle(array []string) {
	random := rand.New(rand.NewSource(time.Now().UnixNano()))
	for i := len(array) - 1; i > 0; i-- {
		j := random.Intn(i + 1)
		array[i], array[j] = array[j], array[i]
	}
}

func Average(xs []float64) float64 {
	total := 0.0
	for _, v := range xs {
		total += v
	}
	return total / float64(len(xs))
}

func Median(numbers []float64) float64 {
	middle := len(numbers) / 2
	result := numbers[middle]
	if len(numbers)%2 == 0 {
		result = (result + numbers[middle-1]) / 2
	}
	return result
}

func main() {
	args := os.Args[1:]

	srcDir := args[0]
	globDir := filepath.Join(srcDir, "*.zip")
	zipfiles, err := filepath.Glob(globDir)
	if err != nil {
		log.Fatal(err)
	}
	Shuffle(zipfiles)
	speeds := make([]float64, 0)
	for _, zipfilename := range zipfiles {
		_, filename := filepath.Split(zipfilename)
		content, err := ioutil.ReadFile(zipfilename)
		if err != nil {
			log.Fatal(err)
		}
		tmpdir, err := ioutil.TempDir("", "extracthere")
		if err != nil {
			log.Fatal(err)
		}

		size := int64(len(content))
		t0 := time.Now()
		DumpAndExtract(tmpdir, content, filename)
		t1 := time.Now()
		os.RemoveAll(tmpdir) // clean up
		speed := float64(size) / t1.Sub(t0).Seconds()
		speeds = append(speeds, speed)
		fmt.Printf(
			"%v/s         %v          %v\n",
			byten.Size(int64(speed)),
			byten.Size(size),
			t1.Sub(t0).Seconds(),
		)

	}
	fmt.Println("")
	fmt.Printf("Average speed:    %v/s\n",
		byten.Size(int64(Average(speeds))))
	fmt.Printf("Median speed:     %v/s\n",
		byten.Size(int64(Median(speeds))))

}
